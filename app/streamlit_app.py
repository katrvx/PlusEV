"""+EV MVP app.   streamlit run app/streamlit_app.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plusev import regime as rg  # noqa: E402
from plusev.execution import simulate, strategy_decider  # noqa: E402
from plusev.governor import Governor  # noqa: E402
from plusev.strategies import DESCRIPTIONS, STRATEGIES  # noqa: E402

st.set_page_config(page_title="+EV", page_icon="📈", layout="wide")

GREEN, RED, GREY, AMBER, BLUE = "#22c55e", "#ef4444", "#64748b", "#f59e0b", "#60a5fa"
STATUS_COLOUR = {"green": GREEN, "red": RED, "neutral": GREY, "thin": "#334155"}

EVAL = ROOT / "eval/mvp"
if not (EVAL / "summary.json").exists():
    st.error("No results yet. Run `python3 scripts/build.py` first.")
    st.stop()

summary = json.loads((EVAL / "summary.json").read_text())
thr = rg.load(ROOT / "envelopes/regime_thresholds.json")
kit_check = json.loads((EVAL / "kit_check.json").read_text()) if (EVAL / "kit_check.json").exists() else None


@st.cache_data
def load_dev_cases(folder: str) -> dict:
    out = {}
    for line in Path(folder).joinpath("inputs.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row.get("task") == "markets":
            out[row["case_id"]] = row["input"]
    return out


def envelope(name: str) -> dict:
    return json.loads((ROOT / f"envelopes/{name}.json").read_text())


def pct(x: float, d: int = 2) -> str:
    return f"{x * 100:+.{d}f}%"


# ------------------------------------------------------------------ header
st.title("+EV")
st.markdown("#### Is your trading bot still worth running?")
st.caption("AgentVerse 2026 · Finance track · MVP. " + f"Data: {summary['data']}. Commit `{summary['commit']}`.")

c1, c2, c3 = st.columns(3)
c1.markdown("**1 · Tag every trade with the market's weather**  \nAt the moment each trade was entered: was volatility low, mid or high? Was there a volatility shock? Was the market trending up, down, or chopping sideways? Computed from prices seen so far only.")
c2.markdown("**2 · A frozen judge learns where the bot wins and loses**  \nFor each weather bucket: does the bot do better or worse there? Stationary bootstrap, correction for every hypothesis tried, then confirmation on a sealed holdout it never saw.")
c3.markdown("**3 · The governor lets it trade only where it has earned it**  \nEvery bar the bot proposes buy/hold/sell. If the current weather is confirmed *red* for this bot, +EV blocks the entry or exits. No evidence, no interference.")
st.info("**Agents propose, code decides.** LLM agents (next step) suggest which weather should matter for a strategy and explain verdicts in plain words. Every number and every decision comes from deterministic code you can audit.")

with st.sidebar:
    st.header("Strategy")
    name = st.selectbox("Base bot", list(STRATEGIES), format_func=lambda s: s.replace("_", " "))
    st.caption(DESCRIPTIONS[name])
    s = summary["strategies"][name]
    st.metric("Hypotheses tested", s["proposed"])
    st.metric("Survived correction (train)", s["survived_training"])
    st.metric("Confirmed on sealed holdout", s["confirmed_holdout"])
    if kit_check:
        ok = kit_check["total_mismatches"] == 0
        st.markdown(("✅" if ok else "⚠️") + f" Our simulator matches the organisers' runner on **{kit_check['total_paths'] - kit_check['total_mismatches']}/{kit_check['total_paths']}** path runs.")

env = envelope(name)
tab1, tab2, tab3, tab4, tab5 = st.tabs(["1 · X-ray", "2 · Governor on one path", "3 · Does it help?", "4 · Kill or Keep", "How it works"])

# ------------------------------------------------------------------ X-ray
with tab1:
    st.subheader(f"Where does the {name.replace('_', ' ')} bot make and lose money?")
    df = pd.DataFrame(env["buckets"])
    df["label"] = df["feature"] + " = " + df["bucket"]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["label"], x=df["effect_train"] * 100, orientation="h",
        marker_color=[STATUS_COLOUR[x] for x in df["status"]],
        error_x=dict(type="data", symmetric=False,
                     array=(df["ci_train"].str[1] - df["effect_train"]) * 100,
                     arrayminus=(df["effect_train"] - df["ci_train"].str[0]) * 100, color="#94a3b8"),
        hovertext=[f"n={n} trades, p={p:.3f}, status={st_}" for n, p, st_ in zip(df["n_train"], df["p_train"], df["status"])],
    ))
    fig.add_vline(x=0, line_color="#94a3b8")
    fig.update_layout(height=380, template="plotly_dark", xaxis_title="Net return per trade in this bucket minus outside it (percentage points, 90% CI)", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    red = [f"**{b['feature']} = {b['bucket']}**" for b in env["buckets"] if b["status"] == "red"]
    green = [f"**{b['feature']} = {b['bucket']}**" for b in env["buckets"] if b["status"] == "green"]
    lines = [f"Across {env['n_train_trades']} training trades the bot averages {pct(env['mean_net_return_train'], 3)} per trade after costs."]
    lines.append(f"{env['hypotheses_proposed']} weather buckets were tested; {env['survived_training']} survived the false-discovery correction (q = {env['fdr_q']}) and {env['confirmed_holdout']} were confirmed on {env['n_holdout_trades']} holdout trades it had never seen.")
    if red:
        lines.append("Confirmed **red** (the bot loses noticeably more here): " + ", ".join(red) + ". The governor will keep it out of these conditions.")
    if green:
        lines.append("Confirmed **green**: " + ", ".join(green) + ".")
    if not red and not green:
        lines.append("No weather bucket has confirmed evidence either way, so **the governor will not interfere** with this bot. That is the intended behaviour: no evidence, no meddling.")
    st.markdown("  \n".join(lines))
    st.caption("Explanation generated by a fixed template from the judge's numbers. In the full system an LLM writes it, and code rejects any sentence containing a number that isn't in the judge's output.")
    with st.expander("Full table"):
        show = df[["label", "n_train", "effect_train", "p_train", "survived_bh", "n_holdout", "effect_holdout", "status"]].copy()
        st.dataframe(show, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ governor on one path
with tab2:
    cases = load_dev_cases(str(ROOT / "data/kit-dev"))
    rows = json.loads((EVAL / f"dev_{name}.json").read_text())
    changed = [r["case_id"] for r in rows if r["blocked"]]
    pool = changed or [r["case_id"] for r in rows]
    st.subheader("The bot proposes, +EV disposes")
    st.caption(f"Dev paths never used to build anything. {len(changed)} of {len(rows)} paths were changed by the governor for this bot.")
    cid = st.selectbox("Path", pool, format_func=lambda c: c[:10])
    case = cases[cid]
    strat = STRATEGIES[name]
    gov = Governor(strat, env, thr)
    raw = simulate(case, strategy_decider(strat), thr, cid)
    gvd = simulate(case, gov.decide, thr, cid)
    prices = case["prices_pence"]
    reds = {(b["feature"], b["bucket"]) for b in env["buckets"] if b["status"] == "red"}

    fig = go.Figure()
    for t in range(len(prices)):
        reg = rg.regime_at(prices, t, thr)
        if reg and any((f, reg[f]) in reds for f in rg.FEATURES):
            fig.add_vrect(x0=t - 0.5, x1=t + 0.5, fillcolor=RED, opacity=0.15, line_width=0)
    fig.add_trace(go.Scatter(y=[p / 100 for p in prices], mode="lines", name="price", line=dict(color="#e2e8f0")))
    for tr in raw["trades"]:
        fig.add_trace(go.Scatter(x=[tr["entry_fill_bar"]], y=[tr["entry_fill_px"] / 100], mode="markers", marker=dict(symbol="triangle-up", size=11, color=AMBER), name="raw buy", showlegend=False))
    for tr in gvd["trades"]:
        fig.add_trace(go.Scatter(x=[tr["entry_fill_bar"]], y=[tr["entry_fill_px"] / 100], mode="markers", marker=dict(symbol="triangle-up", size=15, color=GREEN, line=dict(width=1, color="white")), name="governed buy", showlegend=False))
    fig.update_layout(height=330, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), yaxis_title="price (£)", xaxis_title="bar", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Red bands: bars where the market's weather is confirmed red for this bot. Amber ▲ raw bot entries · green ▲ entries the governor allowed.")

    cap = case["initial_cash_pence"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Raw bot", pct(raw["profit_pence"] / cap), f"max drawdown {raw['max_drawdown'] * 100:.1f}%", delta_color="off")
    m2.metric("Governed by +EV", pct(gvd["profit_pence"] / cap), f"max drawdown {gvd['max_drawdown'] * 100:.1f}%", delta_color="off")
    from plusev.execution import buy_and_hold
    m3.metric("Buy and hold", pct((buy_and_hold(case) - cap) / cap))
    m4.metric("Trades raw → governed", f"{len(raw['trades'])} → {len(gvd['trades'])}")

    eq = go.Figure()
    eq.add_trace(go.Scatter(y=np.array(raw["equity"]) / cap, name="raw", line=dict(color=AMBER)))
    eq.add_trace(go.Scatter(y=np.array(gvd["equity"]) / cap, name="governed", line=dict(color=GREEN)))
    eq.update_layout(height=220, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), yaxis_title="equity / start")
    st.plotly_chart(eq, use_container_width=True)
    log = pd.DataFrame(gvd["decisions"])
    st.markdown("**Governor decision log** (every override has a reason)")
    st.dataframe(log[log["reason"].str.startswith(("BLOCKED", "EXIT"))] if changed else log.tail(10), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ does it help
with tab3:
    paired = sorted((ROOT / "eval/challenge").glob("*/paired.json"))
    if paired:
        st.subheader("Hidden test (organisers' bench, challenge mode)")
        st.caption("Governed bot run in challenge mode: secret seed committed before the run, cases built in memory only, zero provenance warnings. "
                   "Then the raw bot replayed on exactly the same hidden paths from the revealed seed, so the comparison is path by path.")
        prow = []
        for p in paired:
            d = json.loads(p.read_text())
            m = d.get("challenge_market_stats_governed") or {}
            prow.append({
                "pack": d["pack"], "bot": d["strategy"].replace("_", " "), "hidden paths": d["paths_paired"],
                "governed − raw return (90% CI)": f"{pct(d['governed_minus_raw_return']['mean'])} [{pct(d['governed_minus_raw_return']['ci90'][0])}, {pct(d['governed_minus_raw_return']['ci90'][1])}]",
                "governed − raw max drawdown (90% CI)": f"{pct(d['governed_minus_raw_max_drawdown']['mean'])} [{pct(d['governed_minus_raw_max_drawdown']['ci90'][0])}, {pct(d['governed_minus_raw_max_drawdown']['ci90'][1])}]",
                "governed better / worse / identical": f"{d['governed_better']} / {d['raw_better']} / {d['identical']}",
                "governed vs buy & hold (wins–losses, p)": f"{m.get('wins_vs_buy_and_hold')}–{m.get('losses_vs_buy_and_hold')}, p={m.get('sign_test_p_value', float('nan')):.2g}",
                "provenance warnings": len(d.get("provenance_warnings") or []),
            })
        st.dataframe(pd.DataFrame(prow), use_container_width=True, hide_index=True)
        st.markdown("Read it like this: where the bot has a confirmed bad regime, +EV changes the outcome; where it has none, +EV changes **nothing**, path for path.")
        st.divider()
    st.subheader("Across all dev paths: raw bot vs governed vs buy-and-hold")
    st.caption("Practice data. Quote only challenge-mode results from the organisers' bench as evidence.")
    table = []
    for n_, s_ in summary["strategies"].items():
        table.append({
            "bot": n_.replace("_", " "),
            "mean return raw": pct(s_["dev_mean_return"]["raw"]),
            "mean return governed": pct(s_["dev_mean_return"]["governed"]),
            "buy & hold": pct(s_["dev_mean_return"]["buy_and_hold"]),
            "mean max DD raw": f"{s_['dev_mean_drawdown']['raw'] * 100:.2f}%",
            "mean max DD governed": f"{s_['dev_mean_drawdown']['governed'] * 100:.2f}%",
            "governed − raw (90% CI)": f"{pct(s_['governed_minus_raw_return']['mean'])} [{pct(s_['governed_minus_raw_return']['ci90'][0])}, {pct(s_['governed_minus_raw_return']['ci90'][1])}]",
            "paths changed": s_["paths_changed_by_governor"],
            "red regimes": ", ".join(s_["red"]) or "none",
        })
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
    rows = json.loads((EVAL / f"dev_{name}.json").read_text())
    d = [r["gov_ret"] - r["raw_ret"] for r in rows if r["blocked"]]
    if d:
        h = go.Figure(go.Histogram(x=np.array(d) * 100, marker_color=BLUE, nbinsx=30))
        h.add_vline(x=0, line_color="#94a3b8")
        h.update_layout(height=260, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10), title=f"{name.replace('_', ' ')}: governed minus raw return on the {len(d)} paths the governor changed", xaxis_title="percentage points")
        st.plotly_chart(h, use_container_width=True)
    else:
        st.markdown(f"The governor changed **no** paths for {name.replace('_', ' ')}: no confirmed red weather, so it stayed out of the way.")

# ------------------------------------------------------------------ kill or keep
with tab4:
    st.subheader("Your bot is losing. Broken, or just unlucky?")
    positive = [n_ for n_ in STRATEGIES if envelope(n_)["mean_net_return_train"] > 0]
    if not positive:
        st.warning("No base bot has a positive backtest edge on this data; Kill or Keep needs one.")
        st.stop()
    kk_name = st.selectbox("Bot (only bots with a positive backtest edge make sense here)", positive,
                           index=positive.index("trend") if "trend" in positive else 0,
                           format_func=lambda s: s.replace("_", " "), key="kk_bot")
    kk = json.loads((EVAL / f"killorkeep_{kk_name}.json").read_text())
    which = st.radio("Live stream", ["alive", "dying"], horizontal=True,
                     format_func=lambda x: "Bot that still works" if x == "alive" else "Bot whose edge silently dies (hidden trade T)")
    stream = kk["streams"][which]
    ks = sorted(int(k) for k in stream["verdicts"])
    k = st.select_slider("Live trades so far", options=ks, value=ks[min(3, len(ks) - 1)])
    v = stream["verdicts"][str(k)]
    rec_colour = {"keep": GREEN, "reduce": AMBER, "pause": AMBER, "stop": RED}[v["recommendation"]]
    st.markdown(f"<div style='padding:14px;border-radius:10px;background:{rec_colour}22;border:1px solid {rec_colour}'><b style='color:{rec_colour};font-size:1.3em'>{v['recommendation'].upper()}</b> &nbsp; {v['reason']}</div>", unsafe_allow_html=True)
    a, b, c, d_ = st.columns(4)
    a.metric("Drawdown percentile vs own backtest", f"{v['drawdown_percentile']:.0f}th")
    b.metric("Evidence edge is alive (e-value)", f"{v['e_value_alive']:.2f}", "decision at 10", delta_color="off")
    c.metric("Evidence edge has decayed (e-value)", f"{v['e_value_decay']:.2f}", "decision at 10", delta_color="off")
    d_.metric("More trades to a decision (projection)", f"≈{v['trades_to_decision']['median']}", f"80%: {v['trades_to_decision']['p10']}–{v['trades_to_decision']['p90']}", delta_color="off")
    e = go.Figure()
    e.add_trace(go.Scatter(y=v["e_alive_path"], name="edge alive", line=dict(color=GREEN)))
    e.add_trace(go.Scatter(y=v["e_decay_path"], name="edge decayed", line=dict(color=RED)))
    e.add_hline(y=10, line_dash="dash", line_color="#94a3b8", annotation_text="decide (1/α = 10)")
    if which == "dying":
        e.add_vline(x=kk["T_hidden"], line_dash="dot", line_color=AMBER, annotation_text="edge actually died here (hidden)")
    e.update_layout(height=300, template="plotly_dark", yaxis_type="log", margin=dict(l=10, r=10, t=10, b=10), xaxis_title="live trade #", yaxis_title="e-value (log)")
    st.plotly_chart(e, use_container_width=True)
    st.caption("Betting e-processes: under 'no edge' (or 'edge unchanged') the wealth can only reach 10 with probability ≤ 10%, however often you look (Ville's inequality). 'Trades to decision' is a projection assuming future trades resemble the backtest. The dying stream switches to random entries at the hidden trade T; this is labelled synthetic.")

# ------------------------------------------------------------------ how it works
with tab5:
    st.markdown("""
**Pipeline**

| Step | What | Code or LLM |
|---|---|---|
| Regime engine | volatility, volatility shock, trend at every bar, from past prices only | code |
| Base bots | mean reversion, trend, breakout | code |
| Execution | the organisers' fill rules re-implemented; matches their runner to the penny | code |
| X-ray judge | per-regime test, stationary bootstrap, Benjamini–Hochberg, sealed holdout | code |
| Governor | blocks entries / exits in confirmed red regimes | code |
| Kill or Keep | drawdown percentile, betting e-processes, trades-to-decision | code |
| Hypothesis swarm | proposes which regimes should matter, from the strategy's description, before seeing P&L | LLM (next) |
| Explainer | turns verdicts into plain language; numbers checked against the judge | LLM (next; template now) |

**Why agents never decide.** Recent work (Nov 2026) found LLM research agents claim predictability in *no-signal* data 34–44% of the time when allowed to judge. So they propose and explain; a frozen, deterministic judge decides.

**Honest limits.** The hidden test has prices only, so news and event regimes are not used there. Regime maps are learned on training paths and frozen before any evaluation. Practice-data numbers are not evidence; challenge-mode results are.

**Run it** (`K` = the kit's bench script inside the `agentverse` folder)
```
python3 $K generate --pack markets --cases 600 --seed 101 --output data/kit-train
python3 $K generate --pack markets --cases 200 --seed 202 --output data/kit-dev
python3 $K generate --pack markets --cases 200 --seed 303 --output data/kit-holdout
python3 scripts/build.py && python3 scripts/kit_check.py
streamlit run app/streamlit_app.py
```
""")
