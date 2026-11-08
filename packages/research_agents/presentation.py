"""Plain-language presentation of an investigation report, for judges and newcomers.

Built by code from fields already in the report (and, optionally, the one held-out look and the published
strategy verdict). It adds no new numbers and changes no decision: every figure is copied or formatted from the
report, and every item keeps its evidence ids. It is an optional field; existing consumers can ignore it.

Rules this module keeps:
- "Checked" never implies "passed". A filter's outcome is one of: rejected, not_run, selected_for_further_testing,
  approved (only when explicitly supported), reference (a comparison, never a candidate).
- Research stages are called Training, Validation and Held-out test.
- Anything missing says "Not recorded" with a reason.
- The takeaway returns the strategy definition only when one is supplied or known; otherwise it says what we have.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

PRESENTATION_VERSION = 1
STAGE = {"train": "Training", "validation": "Validation", "test": "Held-out test"}
NOT_RECORDED = "Not recorded"

FEATURE_LABEL = {
    "momentum_24h": "24-hour price momentum",
    "momentum_7d": "7-day price momentum",
    "realized_vol_7d": "7-day volatility",
    "atr_14": "14-bar average true range",
    "price_drawdown": "distance below the recent high",
    "volume_zscore": "trading volume vs its 7-day normal (a volume proxy, not liquidity)",
    "vol_ratio_24h_7d": "24-hour volatility vs its 7-day baseline",
    "fear_greed": "Fear & Greed index",
    "news_sentiment": "news sentiment",
}
REGIME_LABEL = {
    "trend_regime": {"bull": "an up-trend", "bear": "a down-trend", "sideways": "a sideways market"},
    "vol_regime": {"high": "high volatility", "low": "low volatility"},
    "liquidity_regime": {"deep": "deep liquidity", "thin": "thin liquidity"},
    "sentiment_regime": {"greed": "greedy sentiment", "fear": "fearful sentiment", "neutral": "neutral sentiment"},
}

# The two demo strategies whose definitions the team supplied (A/kok_a/strategies.py). Anything else is described
# from what the report actually holds: positions and a strategy id.
KNOWN_DEFINITIONS = {
    "btc-trend-24-72-demo": {
        "name": "BTC trend 24/72",
        "rule": "Long BTCUSDT when the 24-hour moving average of the close is above the 72-hour average; otherwise flat.",
        "parameters": {"fast_bars": 24, "slow_bars": 72, "bar": "1h", "side": "long or flat"},
        "source": "A/kok_a/strategies.py (_trend, version trend-sma-24-72-v1)",
    },
    "btc-meanrev-48-demo": {
        "name": "BTC mean reversion 48",
        "rule": "Buy BTCUSDT when the 48-hour z-score of the close falls below -1; sell when it returns to 0.",
        "parameters": {"window_bars": 48, "entry_z": -1.0, "exit_z": 0.0, "bar": "1h", "side": "long or flat"},
        "source": "A/kok_a/strategies.py (_mean_reversion, version meanrev-z48-v1)",
    },
}

GLOSSARY = [
    ("Original strategy", "The strategy exactly as supplied, always on. Nothing here changes its signals."),
    ("Filter", "A rule that only changes position size (0, half or full) depending on market conditions. Also called a gate."),
    ("Training", "The oldest data. Agents may study it and try filters on it."),
    ("Validation", "Later data the agents never saw. Code scores each proposed filter here, once."),
    ("Held-out test", "The newest data, sealed. Opened once, after the selection is committed, and never used to choose."),
    ("pp", "Percentage points: the difference between two returns, e.g. -29% vs -56% is +27 pp."),
    ("90% interval", "The range the result would likely fall in on similar data. If it contains zero, the effect is not proven."),
    ("Critic", "An AI agent whose job is to find reasons a filter will not hold up. It can reject a filter; it cannot approve one by itself."),
    ("Same average size", "A constant position equal to the filter's average Training size. If the filter can't beat it, it only won by holding less."),
    ("Training folds", "Three slices of the Training data used as a stability check. Not unseen data."),
]

Outcome = Literal["rejected", "not_run", "selected_for_further_testing", "approved", "reference"]
OUTCOME_LABEL = {
    "rejected": "Rejected",
    "not_run": "Not run",
    "selected_for_further_testing": "Selected for further testing",
    "approved": "Approved",
    "reference": "Comparison only",
}


class Headline(BaseModel):
    finding: str
    meaning: str
    next_action: str
    verdict: str | None = None                 # published strategy verdict, e.g. KILL, when supplied
    verdict_label: str = NOT_RECORDED
    verdict_scope: str = ""                    # what the verdict applies to
    verdict_source: str = ""


class StageSummary(BaseModel):
    stage: Literal["Training", "Validation", "Held-out test"]
    window: str = NOT_RECORDED
    what_happened: str
    result: str = NOT_RECORDED
    evidence_ids: list[str] = Field(default_factory=list)


class HeldOutResult(BaseModel):
    looked_at: str | None = None
    vs_original_pp: float | None = None
    vs_original_ci_pp: tuple[float, float] | None = None
    own_return: float | None = None
    original_return: float | None = None
    max_drawdown: float | None = None
    original_max_drawdown: float | None = None
    summary: str
    source: str | None = None


class TimingCheck(BaseModel):
    """Did the filter choose WHEN, or just hold less? Validation, identical costs. Diagnostic, not the selection rule."""
    vs_half_size_pp: float | None = None
    vs_same_average_size_pp: float | None = None
    same_average_size: float | None = None      # constant size equal to the filter's average Training size
    vs_validation_size_pp: float | None = None  # vs a constant at the filter's actual Validation size (diagnostic)
    validation_size: float | None = None
    size_note: str | None = None                # when the condition's frequency changed between Training and Validation
    read: str
    source: str


class CheckedFilter(BaseModel):
    policy_id: str
    label: str                                  # short human name
    plain_rule: str                             # what the rule does, in words
    exposure_change: str                        # how it changes position size
    proposed_by: str                            # "Proposer agent", "Reference rule (Lane A)", ...
    stages_checked: list[str]                   # Training / Training folds / Validation / Held-out test
    outcome: Outcome
    outcome_label: str
    reason: str                                 # one line: why this outcome
    validation_vs_original_pp: float | None = None
    validation_vs_original_ci_pp: tuple[float, float] | None = None
    validation_own_return: float | None = None  # its own net return on Validation (= vs cash)
    average_size_on_validation: float | None = None
    held_out: HeldOutResult | None = None
    timing: TimingCheck | None = None
    details: list[str] = Field(default_factory=list)     # full arbiter/critic lines, secondary
    spec: dict | None = None                    # exact settings, secondary
    evidence_ids: list[str] = Field(default_factory=list)


class TraceStep(BaseModel):
    step: int
    actor: str                                  # "Diagnostic agent", "Code: scoring", ...
    actor_kind: Literal["AI agent", "Code"]
    action: Literal["proposed", "checked", "challenged", "decided"]
    title: str
    summary: str
    items: list[str] = Field(default_factory=list)
    changed_conclusion: str | None = None       # how this step changed what the report concludes
    evidence_ids: list[str] = Field(default_factory=list)


class StrategyTakeaway(BaseModel):
    strategy_id: str
    what_we_have: Literal["definition", "positions_and_reference", "positions_only"]
    name: str | None = None
    rule: str | None = None
    parameters: dict | None = None
    source: str | None = None
    runnable_code_included: bool = False
    note: str


class Takeaway(BaseModel):
    strategy: StrategyTakeaway
    selected_filter: dict | None = None         # {policy_id, plain_rule, status, spec}
    selected_filter_note: str
    evidence: list[dict] = Field(default_factory=list)   # [{label, evidence_id | path}]
    plans: str = "Nothing here places orders. Any saved paper plan stays saved, not running."


class ReportPresentation(BaseModel):
    version: int = PRESENTATION_VERSION
    headline: Headline
    stages: list[StageSummary]
    filters: list[CheckedFilter]
    filter_counts: dict[str, int]
    trace: list[TraceStep]
    takeaway: Takeaway
    glossary: list[dict]
    generated_by: str = "code (packages/research_agents/presentation.py); no new numbers, no new decisions"


# ------------------------------------------------------------------ formatting helpers

def _pct(x: float | None, signed: bool = True) -> str:
    if x is None:
        return NOT_RECORDED
    return f"{x * 100:+.1f}%" if signed else f"{x * 100:.1f}%"


def _pp(x: float | None) -> str:
    return NOT_RECORDED if x is None else f"{x * 100:+.1f} pp"


def _ci_pp(ci) -> str:
    if not ci or ci[0] is None or ci[1] is None:
        return ""
    return f" (90% interval {ci[0] * 100:+.1f} to {ci[1] * 100:+.1f} pp)"


def _num(x: float) -> str:
    if abs(x) >= 100 or float(x).is_integer():
        return f"{x:g}"
    return f"{x:.4g}"


def _size(a: float) -> str:
    return {0.0: "no position", 0.5: "half size", 1.0: "full size"}.get(float(a), f"{a:g}x size")


EVIDENCE_PAREN = re.compile(r"\s*\([^()]*\bev_[a-z_]+_[0-9a-f]{10}[^()]*\)")
EVIDENCE_REF = re.compile(r"\s*\b(?:in |see )?ev_[a-z_]+_[0-9a-f]{10}\b")


def _first_sentence(text: str, limit: int = 220) -> str:
    text = " ".join(EVIDENCE_REF.sub("", EVIDENCE_PAREN.sub("", str(text))).split())
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def _condition_text(c: dict) -> str:
    feat = FEATURE_LABEL.get(c.get("feature"), str(c.get("feature")))
    op = "is above" if c.get("op") == ">" else "is at or below"
    return f"{feat} {op} {_num(float(c['threshold']))}"


def _rule_text(spec: dict) -> tuple[str, str]:
    """(plain rule, exposure change) for a threshold gate; generic text otherwise."""
    conds = spec.get("conditions")
    at, af = spec.get("allocation_when_true"), spec.get("allocation_when_false")
    if conds and at is not None and af is not None:
        when = " and ".join(_condition_text(c) for c in conds)
        rule = f"When {when}: {_size(at)}. Otherwise: {_size(af)}. Thresholds were set on Training data."
        lower = min(at, af)
        change = f"Never adds risk: it only cuts the position to {_size(lower)} when the condition is " \
                 f"{'not ' if at > af else ''}met."
        return rule, change
    return ("A rule supplied by Lane A; its exact settings are in the spec.",
            "Changes position size between 0, half and full by market regime.")


def _avg_size(mix: dict) -> float | None:
    if not mix:
        return None
    try:
        return sum(float(k) * float(v) for k, v in mix.items())
    except (TypeError, ValueError):
        return None


def _regime_text(cond: str) -> str:
    feat, _, bucket = cond.partition("=")
    return REGIME_LABEL.get(feat, {}).get(bucket, cond.replace("_", " "))


def _label(policy_id: str, spec: dict | None, source: str) -> str:
    if policy_id == "rule::regime_filter":
        return "Lane A regime filter"
    if policy_id.startswith("rule::half_size"):
        return "Constant half size"
    if policy_id.startswith("meta::lgbm"):
        return "LightGBM model filter"
    if policy_id.startswith("rule::"):
        return "Simple reference rule"
    conds = (spec or {}).get("conditions") or []
    if conds:
        at, af = spec.get("allocation_when_true"), spec.get("allocation_when_false")
        lower = af if at > af else at
        cut = "Flat" if lower == 0 else "Half size"
        parts = []
        for c in conds:
            side = "low" if (c.get("op") == ">") == (at > af) else "high"
            feat = FEATURE_LABEL.get(c.get("feature"), c.get("feature"))
            mark = "≤" if side == "low" else ">"
            parts.append(f"{feat} is {side} ({mark} {_num(float(c['threshold']))})")
        return f"{cut} when " + ((" or " if at > af else " and ").join(parts))
    return policy_id.split("::", 1)[-1]


def _blocking_reason(reasons: list[str]) -> str:
    for r in reasons:
        if r.startswith("critic (blocking):"):
            return "The critic rejected it: " + _first_sentence(r.split(":", 1)[1], 180)
    for r in reasons:
        if r.startswith("critic veto"):
            return "The critic rejected it."
    for r in reasons:
        low = r.lower()
        if "does not beat always-on" in low:
            return "It did not beat the original strategy on Validation after costs."
        if "does not beat cash" in low or "loses money" in low:
            return "It did not beat holding cash on Validation."
        if low.startswith("degenerate"):
            return "It barely changed anything: one position size on almost every decision."
    return _first_sentence(reasons[0]) if reasons else NOT_RECORDED


# ------------------------------------------------------------------ the presenter

def present(report: dict | BaseModel, *, held_out: dict | None = None, published: dict | None = None,
            definition: dict | None = None, windows: dict | None = None,
            report_path: str | None = None, held_out_path: str | None = None,
            timing_check: dict | None = None) -> ReportPresentation:
    """Build the plain-language view of one report.

    held_out:   the one held-out look (frozen_look_*.json), if taken.
    published:  the published strategy verdict, e.g. {"verdict": "KILL", "reason": "...", "source": "Lane A arbiter"}.
    definition: the original strategy definition, if supplied ({name, rule, parameters, source}).
    windows:    {"train": "...", "validation": "...", "test": "..."} date ranges, if known.
    """
    r = report.model_dump(mode="json") if isinstance(report, BaseModel) else report
    windows = windows or {}
    candidates = r.get("candidates") or []
    trials = r.get("trial_log") or []
    champion_id = r.get("champion_policy_id")
    evaluation = (held_out or {}).get("evaluation") or {}
    look_policy = (held_out or {}).get("champion_policy_id")

    filters = _filters(r, candidates, trials, evaluation if look_policy else {}, look_policy, held_out, held_out_path,
                       timing_check)
    counts = {k: sum(1 for f in filters if f.outcome == k) for k in OUTCOME_LABEL}
    headline = _headline(r, filters, published, evaluation if look_policy else {}, champion_id)
    stages = _stages(r, trials, windows, evaluation, published, held_out, look_policy)
    trace = _trace(r, filters, trials, published, held_out)
    takeaway = _takeaway(r, filters, definition, report_path, held_out_path, champion_id)
    return ReportPresentation(headline=headline, stages=stages, filters=filters, filter_counts=counts, trace=trace,
                              takeaway=takeaway, glossary=[{"term": t, "meaning": m} for t, m in GLOSSARY])


def _held_out_result(evaluation: dict, held_out: dict | None, path: str | None) -> HeldOutResult:
    m, a = evaluation.get("metrics") or {}, evaluation.get("always_on") or {}
    delta, ci = evaluation.get("delta_net_return_vs_always_on"), evaluation.get("ci_delta")
    own, orig = m.get("net_return"), a.get("net_return")
    parts = [f"Beat the original by {_pp(delta)}{_ci_pp(ci)}." if delta is not None and delta > 0
             else f"Versus the original: {_pp(delta)}{_ci_pp(ci)}."]
    if m.get("max_drawdown") is not None and a.get("max_drawdown") is not None:
        parts.append(f"Worst drawdown {_pct(a['max_drawdown'], False)} → {_pct(m['max_drawdown'], False)}.")
    if own is not None:
        parts.append(f"Its own return was {_pct(own)}" + (" — it still lost money." if own < 0 else "."))
    return HeldOutResult(
        looked_at=(held_out or {}).get("looked_at"), vs_original_pp=delta,
        vs_original_ci_pp=tuple(ci) if ci else None, own_return=own, original_return=orig,
        max_drawdown=m.get("max_drawdown"), original_max_drawdown=a.get("max_drawdown"),
        summary=" ".join(parts), source=path)


def _train_specs(r) -> dict[str, dict]:
    specs = {}
    for e in r.get("evidence") or []:
        if e.get("tool") == "test_gate_train":
            spec = (e.get("payload") or {}).get("policy_spec") or {}
            if spec.get("policy_id"):
                specs[spec["policy_id"]] = spec
    return specs


def _timing(c: dict, timing_check: dict | None) -> TimingCheck | None:
    half, same, size, src = (c.get("validation_delta_vs_half_size"), c.get("validation_delta_vs_matched_exposure"),
                             c.get("matched_exposure"), "this report")
    vsize = vdelta = note = None
    g = next((g for g in (timing_check or {}).get("gates") or [] if g.get("policy_id") == c["policy_id"]
              and g.get("role") == "agent gate"), None)
    if g:
        half, same, size = g.get("vs_half_size"), g.get("vs_matched_exposure"), g.get("train_average_size")
        vsize, vdelta, note = g.get("validation_average_size"), g.get("vs_validation_size"), g.get("size_shift_note")
        src = timing_check.get("_path") or "timing check (Validation)"
    if half is None and same is None:
        return None
    checks = [x for x in (half, same, vdelta) if x is not None]
    if same is not None and all(x > 0 for x in checks):
        read = ("Beat constant half size and a constant of the same average size on Validation: some evidence of "
                "timing, not proof (Validation was also used to select).")
    elif same is not None:
        read = "Did not beat a constant position of the same average size: the gain came from holding less, not timing."
    else:
        read = ("Beat constant half size on Validation." if half > 0 else
                "Did not beat constant half size: the gain came from holding less, not timing.")
    if note:
        read += " Its average size changed between Training and Validation, so treat the comparison with care."
    return TimingCheck(vs_half_size_pp=half, vs_same_average_size_pp=same, same_average_size=size,
                       vs_validation_size_pp=vdelta, validation_size=vsize, size_note=note, read=read, source=src)


def _filters(r, candidates, trials, evaluation, look_policy, held_out, held_out_path, timing_check=None) -> list[CheckedFilter]:
    out: list[CheckedFilter] = []
    train_specs = _train_specs(r)
    by_policy: dict[str, list[dict]] = {}
    for t in trials:
        by_policy.setdefault(t["policy_id"], []).append(t)
    seen = set()
    order = {"agent_champion": 0, "agent_not_selected": 1, "competitor": 2}
    for c in sorted(candidates, key=lambda c: order.get(c.get("role"), 3)):
        pid = c["policy_id"]
        seen.add(pid)
        spec = c.get("policy_spec") or {}
        rule, change = _rule_text(spec)
        tl = by_policy.get(pid, [])
        stages = []
        if any(t["split"] == "train" and t.get("fold") is None and t["source"] == "agent" for t in tl):
            stages.append("Training")
        if any(t.get("fold") is not None for t in tl):
            stages.append("Training folds")
        if any(t["split"] == "validation" and t["status"] == "evaluated" for t in tl) or \
                c.get("validation_delta_vs_always_on") is not None:
            stages.append("Validation")
        ho = None
        if c["role"] == "competitor":
            outcome, reason = "reference", "A comparison the agents' filters must beat. Never a candidate."
            who = "Reference rule (Lane A)" if not pid.startswith("rule::half_size") else "Reference rule (code)"
        elif c["status"] == "accepted_for_frozen_test":
            who = "Proposer agent"
            outcome = "selected_for_further_testing"
            reason = ("Met every condition fixed before the run (beat the original and cash on Validation after costs, "
                      "changed something real, not rejected by the critic), so it earned one held-out test. Selection "
                      "is not approval.")
            if look_policy == pid and evaluation:
                stages.append("Held-out test")
                ho = _held_out_result(evaluation, held_out, held_out_path)
                own = (evaluation.get("metrics") or {}).get("net_return")
                if own is not None and own < 0:
                    reason = ("Earned one held-out test, then lost money there (" + _pct(own) + "), so it is not "
                              "approved. Losing less than the original is not a fix.")
                else:
                    reason = "Earned one held-out test; see the result. Approval is not recorded for this report."
        else:
            who = "Proposer agent"
            outcome, reason = "rejected", _blocking_reason(c.get("reasons") or [])
        out.append(CheckedFilter(
            policy_id=pid, label=_label(pid, spec, c.get("source", "")), plain_rule=rule, exposure_change=change,
            proposed_by=who, stages_checked=stages, outcome=outcome,
            outcome_label=OUTCOME_LABEL[outcome] + (" · not approved" if ho and (ho.own_return or 0) < 0 else ""),
            reason=reason, validation_vs_original_pp=c.get("validation_delta_vs_always_on"),
            validation_vs_original_ci_pp=tuple(c["validation_ci"]) if c.get("validation_ci") else None,
            validation_own_return=c.get("validation_delta_vs_cash"),
            average_size_on_validation=_avg_size(c.get("allocation_mix") or {}), held_out=ho,
            timing=_timing(c, timing_check) if c.get("source") == "agent" else None,
            details=list(c.get("reasons") or []), spec=spec or None, evidence_ids=list(c.get("evidence_ids") or [])))
    # agent filters tried on Training but never proposed: checked once, not taken further
    for pid, tl in by_policy.items():
        if pid in seen or not pid.startswith("agent::"):
            continue
        t0 = tl[0]
        refused = all(t["status"] != "evaluated" for t in tl)
        reason = ("Refused before it ran: " + _first_sentence(t0.get("note") or "outside the allowed rules") if refused
                  else f"Tried on Training ({_pp(t0.get('delta_net_return_vs_always_on'))} vs the original) but the "
                       "agent did not propose it, so it was never checked on Validation.")
        spec = train_specs.get(pid)
        if spec:
            rule, change = _rule_text(spec)
            label = _label(pid, spec, "agent")
        else:
            rule = NOT_RECORDED + ": the settings of this training trial were not kept in the report."
            change, label = NOT_RECORDED, pid.split("::", 1)[-1].replace("_", " ")
        out.append(CheckedFilter(
            policy_id=pid, label=label, plain_rule=rule, spec=spec,
            exposure_change=change, proposed_by="Proposer agent (training trial)",
            stages_checked=[] if refused else ["Training"], outcome="not_run", outcome_label="Not run on Validation",
            reason=reason, evidence_ids=[t["evidence_id"] for t in tl if t.get("evidence_id")]))
    return out


def _headline(r, filters, published, evaluation, champion_id) -> Headline:
    sid = r.get("strategy_id", "this strategy")
    proposed = [f for f in filters if f.proposed_by == "Proposer agent"]
    rejected = [f for f in proposed if f.outcome == "rejected"]
    chosen = next((f for f in filters if f.policy_id == champion_id), None)
    verdict = (published or {}).get("verdict")
    src = (published or {}).get("source", "")
    reason = (published or {}).get("reason", "")
    scope = (published or {}).get("scope", "the original strategy, always on")
    labels = {"KILL": "Kill", "KEEP": "Keep", "INCONCLUSIVE": "Not proven", "MONITOR": "Monitor",
              "CONDITIONAL": "Keep with a filter", "REDUCE": "Reduce", "RESTRICT": "Restrict"}
    label = labels.get(verdict, verdict.title() if verdict else NOT_RECORDED)

    if verdict == "KILL" and chosen and chosen.held_out and (chosen.held_out.own_return or 0) < 0:
        ho = chosen.held_out
        return Headline(
            finding=f"Kill the original strategy. The agents' best filter lost less, but still lost money.",
            meaning=(f"On the held-out test the filter beat the original by {_pp(ho.vs_original_pp)}"
                     f"{_ci_pp(ho.vs_original_ci_pp)}, and its own return was {_pct(ho.own_return)}. "
                     f"Most of that gain comes from holding a smaller position. A filter that loses less is not a "
                     f"new Keep verdict."),
            next_action=("Stop running this strategy. Do not deploy the filter as a fix. Any saved paper plan stays "
                         "saved, not running."),
            verdict=verdict, verdict_label=label, verdict_scope=scope, verdict_source=src)
    if verdict == "INCONCLUSIVE" and not chosen:
        by_critic = sum(1 for f in rejected if f.reason.startswith("The critic"))
        why = (f"The critic rejected {'all of them' if by_critic == len(rejected) else by_critic}; "
               "the reasons are listed with each filter.") if by_critic else ""
        return Headline(
            finding="Not proven. No filter earned the held-out test, so the strategy stays unchanged.",
            meaning=(f"{reason[:1].upper() + reason[1:] if reason else 'The held-out evidence does not settle it.'} "
                     f"The agents proposed {len(proposed)} filter{'s' if len(proposed) != 1 else ''}; "
                     f"{len(rejected)} {'was' if len(rejected) == 1 else 'were'} rejected. {why}").strip(),
            next_action=("Don't add capital or change the strategy on this evidence. Re-test it on data after the "
                         "held-out window. Any saved paper plan stays saved, not running."),
            verdict=verdict, verdict_label=label, verdict_scope=scope, verdict_source=src)
    if verdict:
        return Headline(finding=f"{label}: {reason or 'see the strategy verdict.'}",
                        meaning=(f"The agents proposed {len(proposed)} filter(s); "
                                 + (f"'{chosen.label}' was selected for further testing." if chosen
                                    else "none was selected.")),
                        next_action="Act on the strategy verdict only. Filters are not approved unless marked so.",
                        verdict=verdict, verdict_label=label, verdict_scope=scope, verdict_source=src)
    # no published strategy verdict: say only what the agents' stage decided
    if chosen:
        return Headline(
            finding=f"One filter earned a held-out test: {chosen.label}. Nothing is approved yet.",
            meaning=(f"On Validation it beat the original by {_pp(chosen.validation_vs_original_pp)}"
                     f"{_ci_pp(chosen.validation_vs_original_ci_pp)} and returned "
                     f"{_pct(chosen.validation_own_return)} on its own. The held-out test has not been run."),
            next_action="Commit this report, then run the one held-out test (scripts/frozen_look.py) before acting.",
            verdict_label=NOT_RECORDED, verdict_scope="No strategy verdict was recorded for this report.")
    return Headline(
        finding="No filter earned a held-out test. Keep the strategy unchanged on this evidence.",
        meaning=(f"The agents proposed {len(proposed)} filter(s) and {len(rejected)} {'was' if len(rejected) == 1 else 'were'} "
                 "rejected. Reasons are listed with each filter.") if proposed else
                "The agents found no pattern strong enough to propose a filter, so none was tested.",
        next_action="Use the strategy verdict (Lane A arbiter) for keep or kill; this report does not change it.",
        verdict_label=NOT_RECORDED, verdict_scope="No strategy verdict was recorded for this report.")


def _train_result(r) -> str:
    for e in r.get("evidence") or []:
        if e.get("tool") == "cost_attribution" and (e.get("args") or {}).get("split") == "train":
            pay = e.get("payload") or {}
            base = next((b for b in pay.get("baselines") or [] if b.get("policy") == "always_on"), None)
            cost = (pay.get("costs") or [{}])[0]
            if base and base.get("metrics", {}).get("net_return") is not None:
                m = base["metrics"]
                ci = m.get("ci_net_return")
                fees = (cost.get("fees") or 0) + (cost.get("slippage") or 0)
                return (f"Original strategy {_pct(m['net_return'])} after costs"
                        + (f" (90% interval {_pct(ci[0])} to {_pct(ci[1])})" if ci else "")
                        + (f"; before costs {_pct(cost.get('gross_return'))}" if cost.get("gross_return") is not None else "")
                        + (f", worst drawdown {_pct(m.get('max_drawdown'), False)}" if m.get("max_drawdown") is not None else "")
                        + ".")
    return NOT_RECORDED + ": the Training cost breakdown is not in this report."


def _stages(r, trials, windows, evaluation, published, held_out, look_policy) -> list[StageSummary]:
    n_train = len({t["policy_id"] for t in trials if t["split"] == "train" and t["source"] == "agent" and t.get("fold") is None})
    hyps = (r.get("diagnostic") or {}).get("hypotheses") or []
    train_ev = sorted({e for h in hyps for e in h.get("evidence_ids", [])})[:6]
    always = r.get("validation_always_on") or {}
    blocks = ((r.get("strategy_health") or {}).get("validation_blocks") or [])
    val_window = windows.get("validation") or (f"from {blocks[0]['start'][:10]}, {len(blocks)} two-week blocks"
                                                if blocks else NOT_RECORDED)
    n_val = len({t["policy_id"] for t in trials if t["split"] == "validation" and t["status"] == "evaluated"})
    val_ev = [t["evidence_id"] for t in trials if t["split"] == "validation" and t.get("evidence_id")][:8]
    stages = [
        StageSummary(stage="Training", window=windows.get("train", NOT_RECORDED),
                     what_happened=(f"The agents studied when the strategy makes and loses money, found "
                                    f"{len(hyps)} pattern(s), and tried {n_train} filter(s) on this data only."),
                     result=_train_result(r), evidence_ids=train_ev),
        StageSummary(stage="Validation", window=val_window,
                     what_happened=(f"Code scored {n_val} rule(s) once on data the agents never saw: their proposals "
                                    f"and the reference rules, after costs."),
                     result=(f"Original strategy {_pct(always.get('net_return'))}"
                             f"{' (90% interval ' + _pct(always['ci_net_return'][0]) + ' to ' + _pct(always['ci_net_return'][1]) + ')' if always.get('ci_net_return') else ''}"
                             f"; cash {_pct(r.get('validation_cash_net_return', 0.0))}."
                             if always.get("net_return") is not None else NOT_RECORDED),
                     evidence_ids=val_ev),
    ]
    if look_policy and evaluation:
        ho = _held_out_result(evaluation, held_out, None)
        stages.append(StageSummary(
            stage="Held-out test", window=windows.get("test", NOT_RECORDED),
            what_happened=(f"Opened once ({(held_out or {}).get('looked_at', '')[:10] or 'date not recorded'}), after "
                           f"the report that chose the filter was committed. Nothing was chosen here."),
            result=ho.summary))
    elif published and published.get("verdict"):
        stages.append(StageSummary(
            stage="Held-out test", window=windows.get("test", NOT_RECORDED),
            what_happened=("Scored once by Lane A's arbiter for the original strategy and its reference rules. "
                           "No agent filter earned a look."),
            result=published.get("reason", NOT_RECORDED)))
    else:
        stages.append(StageSummary(
            stage="Held-out test", window=windows.get("test", NOT_RECORDED),
            what_happened=NOT_RECORDED + ": the held-out test has not been run for this report.",
            result=NOT_RECORDED + ". It runs once, after this report is committed, so it can't be tuned to."))
    return stages


def _trace(r, filters, trials, published, held_out) -> list[TraceStep]:
    steps: list[TraceStep] = []
    diag = r.get("diagnostic") or {}
    hyps = diag.get("hypotheses") or []

    def add(**kw):
        steps.append(TraceStep(step=len(steps) + 1, **kw))

    items = []
    for h in hyps:
        where = ", ".join(_regime_text(c) for c in h.get("conditions") or []) or "some conditions"
        items.append(f"{'Works better' if h.get('direction') == 'works_better' else 'Works worse'} in {where} "
                     f"({h.get('confidence', '?')} confidence)")
    add(actor="Diagnostic agent", actor_kind="AI agent", action="proposed",
        title=f"Found {len(hyps)} pattern(s) in when the strategy works",
        summary=_first_sentence(diag.get("summary", NOT_RECORDED), 260), items=items,
        evidence_ids=sorted({e for h in hyps for e in h.get("evidence_ids", [])})[:8])

    ctx = r.get("context")
    if ctx:
        strong = [f for f in ctx.get("findings") or [] if f.get("strength") == "moderate"]
        add(actor="Context agent", actor_kind="AI agent", action="checked",
            title="Checked market mood around the best and worst weeks",
            summary=_first_sentence(ctx.get("summary", ""), 260),
            items=[_first_sentence(f["statement"], 200) + f" ({f.get('strength')})" for f in ctx.get("findings") or []][:4],
            changed_conclusion=None if strong else "Nothing strong enough to act on; it did not change the filters.",
            evidence_ids=sorted({e for f in ctx.get("findings") or [] for e in f.get("evidence_ids", [])})[:6])
    else:
        add(actor="Context agent", actor_kind="AI agent", action="checked", title="Market mood check",
            summary=NOT_RECORDED + ": this report has no context step (it predates the context agent or it was skipped).")

    proposals = r.get("proposals") or []
    n_train = len({t["policy_id"] for t in trials if t["source"] == "agent" and t["split"] == "train" and t.get("fold") is None})
    add(actor="Proposer agent", actor_kind="AI agent", action="proposed",
        title=f"Tried {n_train} filter(s) on Training, proposed {len(proposals)}",
        summary="Each filter only changes position size. The strategy's own signals are never touched.",
        items=[f"{_label('agent::' + p['proposal_id'], {'conditions': p['conditions'], 'allocation_when_true': p['allocation_when_true'], 'allocation_when_false': p['allocation_when_false']}, 'agent')}: "
               + _first_sentence(p.get("rationale", ""), 160) for p in proposals],
        evidence_ids=sorted({e for p in proposals for e in p.get("evidence_ids", [])})[:8])

    scored = [f for f in filters if "Validation" in f.stages_checked]
    beat = [f for f in scored if f.proposed_by == "Proposer agent" and (f.validation_vs_original_pp or 0) > 0]
    add(actor="Code: scoring", actor_kind="Code", action="checked",
        title=f"Scored {len(scored)} rule(s) on Validation and Training folds",
        summary=(f"{len(beat)} of {len([f for f in scored if f.proposed_by == 'Proposer agent'])} agent filter(s) "
                 f"beat the original on Validation. Reference rules were scored the same way."),
        items=[f"{f.label}: {_pp(f.validation_vs_original_pp)} vs the original, own return "
               f"{_pct(f.validation_own_return)}" for f in scored],
        evidence_ids=[e for f in scored for e in f.evidence_ids[:1]])

    health = r.get("strategy_health")
    if health:
        add(actor="Code: health check", actor_kind="Code", action="checked", title="Asked: unlucky or broken?",
            summary=_first_sentence(health.get("summary", NOT_RECORDED), 260),
            evidence_ids=[health["evidence_id"]] if health.get("evidence_id") else [])

    crit = r.get("critiques") or []
    rejected = [c for c in crit if c.get("verdict") != "approve_for_frozen_test"]
    by_id = {f.policy_id: f for f in filters}
    citems = []
    for c in crit:
        f = by_id.get(f"agent::{c['proposal_id']}")
        why = (c.get("fragile_samples") or c.get("leakage_concerns") or c.get("overfit_risks")
               or c.get("counterexamples") or c.get("observations") or [""])[0]
        citems.append(f"{f.label if f else c['proposal_id']}: {'approved for one held-out test' if c['verdict'] == 'approve_for_frozen_test' else 'rejected'}"
                      + (f" — {_first_sentence(why, 200)}" if why else ""))
    best = max((f for f in filters if f.proposed_by == "Proposer agent" and f.validation_vs_original_pp is not None),
               key=lambda f: f.validation_vs_original_pp, default=None)
    change = None
    if best and best.outcome == "rejected" and "critic" in best.reason.lower():
        change = (f"The filter with the best Validation number ({best.label}, {_pp(best.validation_vs_original_pp)}) "
                  f"was rejected by the critic, so it could not be selected.")
    add(actor="Critic agent", actor_kind="AI agent", action="challenged",
        title=f"Challenged {len(crit)} filter(s): rejected {len(rejected)}",
        summary="The critic looks for leakage, overfitting and fragile samples. It can block a filter, not approve one.",
        items=citems, changed_conclusion=change,
        evidence_ids=sorted({e for c in crit for e in c.get("evidence_ids", [])})[:8])

    chosen = next((f for f in filters if f.policy_id == r.get("champion_policy_id")), None)
    add(actor="Code: selection rule", actor_kind="Code", action="decided",
        title=("Selected one filter for the held-out test" if chosen else "No filter earned the held-out test"),
        summary=("The rule was fixed before the run: beat the original and cash on Validation after costs, change "
                 "something real, and not be rejected by the critic. Only the best such filter goes on."),
        items=[f"Selected: {chosen.label}" if chosen else "Selected: none"]
        + [b.replace("passed the critic", "was not rejected by the critic")
           for b in r.get("verdict_basis") or [] if b.startswith(("champion", "no agent", "none"))][:2],
        changed_conclusion=None)

    look = (held_out or {}).get("evaluation")
    if look and chosen and chosen.held_out:
        add(actor="Code: held-out test", actor_kind="Code", action="checked", title="Opened the held-out test once",
            summary=chosen.held_out.summary,
            changed_conclusion=("Selection did not become approval: the filter still lost money."
                                if (chosen.held_out.own_return or 0) < 0 else None),
            evidence_ids=[])
    if published and published.get("verdict"):
        add(actor=published.get("source") or "Strategy verdict", actor_kind="Code", action="decided",
            title=f"Strategy verdict: {published['verdict']}",
            summary=published.get("reason", NOT_RECORDED),
            items=[f"Applies to: {published.get('scope', 'the original strategy, always on')}"])
    return steps


def _takeaway(r, filters, definition, report_path, held_out_path, champion_id) -> Takeaway:
    sid = r.get("strategy_id", "")
    d = definition or KNOWN_DEFINITIONS.get(sid)
    if d:
        strat = StrategyTakeaway(
            strategy_id=sid, what_we_have="positions_and_reference" if not definition else "definition",
            name=d.get("name"), rule=d.get("rule"), parameters=d.get("parameters"), source=d.get("source"),
            note=("The analysis used this strategy's positions. Its definition and the file that generates them are "
                  "listed here; this report itself contains no runnable code."))
    else:
        strat = StrategyTakeaway(
            strategy_id=sid, what_we_have="positions_only",
            note=("Only the strategy's positions were supplied, not its code or rules, so we can return its "
                  "identifier and the evidence, not a runnable strategy."))
    chosen = next((f for f in filters if f.policy_id == champion_id), None)
    if chosen:
        status = chosen.outcome_label
        sel = {"policy_id": chosen.policy_id, "label": chosen.label, "plain_rule": chosen.plain_rule,
               "status": status, "spec": chosen.spec}
        note = ("Exact settings of the selected filter. " +
                ("It was tested once on held-out data and is not approved." if chosen.held_out
                 else "It has not been through the held-out test, so it is not approved."))
    else:
        sel, note = None, "No filter was selected, so there are no filter settings to take away."
    evidence = []
    if report_path:
        evidence.append({"label": "Full agent report (every claim linked to a tool result)", "path": report_path})
    if held_out_path:
        evidence.append({"label": "The one held-out test look", "path": held_out_path})
    if chosen:
        evidence += [{"label": f"{chosen.label}: scoring evidence", "evidence_id": e} for e in chosen.evidence_ids[:3]]
    if (r.get("strategy_health") or {}).get("evidence_id"):
        evidence.append({"label": "Unlucky or broken check", "evidence_id": r["strategy_health"]["evidence_id"]})
    return Takeaway(strategy=strat, selected_filter=sel, selected_filter_note=note, evidence=evidence)


__all__ = ["ReportPresentation", "present", "KNOWN_DEFINITIONS", "PRESENTATION_VERSION"]
