"""Context agent's tool: what was market sentiment doing around the strategy's best and worst weeks?

Code computes this; the context agent (agents.py) only reads it and writes findings that cite it.
TRAIN only, point-in-time: the Fear & Greed series comes from Lane A's GateRunner.feature_series, which
joins each daily value as of its availability (next day), so nothing here sees a value before it existed.

Pre-registered definitions (fixed before any run):
- a "week" is 168 consecutive hourly bars of the unchanged strategy (always-on net return, compounded);
  the K worst and K best non-overlapping weeks are picked greedily;
- sentiment is "fear" below 50 and "greed" at 50 or above (Alternative.me's neutral line);
  a flip is a change between the two; extreme fear < 25, extreme greed > 75;
- "flip before" = a flip in the 72 bars (3 days) before the week starts;
- base rate = the share of all train start bars that have such a flip in the 72 bars before them;
  a one-sided binomial tail says whether K weeks with that many flips are more than chance.
Small samples: with K = 4 even 4/4 is weak evidence; findings must say so. Co-occurrence is not causation.
Multiple comparisons: four tallies are reported, but only the two PRIMARY ones (worst weeks after a
greed-to-fear flip, best weeks after a fear-to-greed flip) may support a 'moderate' finding, and only at
p < 0.05 (0.10 Bonferroni-corrected for the two). The other two are descriptive.
The base rate is train-wide; where flips cluster (early 2018 flipped about twice as often), a week there
is more likely than the base rate says to follow a flip.
"""

from __future__ import annotations

import math

WEEK = 168
LOOKBACK = 72
NEUTRAL = 50.0
EXTREME_FEAR, EXTREME_GREED = 25.0, 75.0
K = 4
PRIMARY_TALLIES = ("worst_weeks_after_greed_to_fear_flip", "best_weeks_after_fear_to_greed_flip")
MODERATE_P = 0.05          # 0.10 / 2 primary tallies
TALLY_FLAG = {"worst_weeks_after_greed_to_fear_flip": ("worst_weeks", "greed_to_fear_flip_in_prior_3_days"),
              "best_weeks_after_fear_to_greed_flip": ("best_weeks", "fear_to_greed_flip_in_prior_3_days"),
              "worst_weeks_after_fear_to_greed_flip": ("worst_weeks", "fear_to_greed_flip_in_prior_3_days"),
              "best_weeks_after_greed_to_fear_flip": ("best_weeks", "greed_to_fear_flip_in_prior_3_days")}


def _binom_tail(k: int, n: int, p: float) -> float:
    return float(sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def _ffill(values):
    out, last = [], None
    for v in values:
        last = v if v is not None else last
        out.append(last)
    return out


def _flip_flags(fg):
    """g2f[i] / f2g[i]: a flip happened AT bar i (bar i-1 on the other side of the neutral line)."""
    g2f, f2g = [False] * len(fg), [False] * len(fg)
    for i in range(1, len(fg)):
        a, b = fg[i - 1], fg[i]
        if a is None or b is None:
            continue
        g2f[i] = a >= NEUTRAL > b
        f2g[i] = a < NEUTRAL <= b
    return g2f, f2g


def _windows(rets, k, worst: bool, exclude=()):
    n = len(rets)
    if n < WEEK:
        return []
    log = [math.log1p(r) for r in rets]
    cum = [0.0]
    for x in log:
        cum.append(cum[-1] + x)
    scores = [(cum[i + WEEK] - cum[i], i) for i in range(n - WEEK + 1)]
    scores.sort(key=lambda s: s[0], reverse=not worst)
    chosen = []
    for s, i in scores:
        if all(abs(i - j) >= WEEK for _, j in chosen) and all(abs(i - j) >= WEEK for j in exclude):
            chosen.append((s, i))
        if len(chosen) == k:
            break
    return sorted(chosen, key=lambda c: c[1])


def sentiment_episodes(experiment, runner, train_end=None, k: int = K) -> dict:
    """Payload for the context tool, or {"error": ...} when the loader has no sentiment series or equity."""
    fs = getattr(runner, "feature_series", None)
    equity = [p for p in (getattr(experiment, "equity", None) or []) if p.split == "train"]
    if fs is None or not equity:
        return {"error": "no train Fear & Greed series or per-bar equity from this loader"}
    from .news import as_utc
    try:
        series = fs("fear_greed", "train")
        by_time = {as_utc(t): v for t, v in series}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"fear_greed series unavailable: {type(exc).__name__}"}
    if train_end is not None:
        train_end = as_utc(train_end)
        equity = [p for p in equity if as_utc(p.decision_time) <= train_end]
    times = [as_utc(p.decision_time) for p in equity]
    try:
        rets = [float(p.net_return) for p in equity]
    except (TypeError, ValueError):
        return {"error": "train equity has a missing net return"}
    if not all(math.isfinite(r) for r in rets):
        return {"error": "train equity has non-finite net returns"}
    fg = _ffill([by_time.get(t) for t in times])
    if sum(v is not None for v in fg) < WEEK:
        return {"error": "too little Fear & Greed coverage on train"}
    g2f, f2g = _flip_flags(fg)

    def flip_before(flags, i):
        return any(flags[max(0, i - LOOKBACK):i + 1])

    starts = range(len(times) - WEEK + 1)
    base_g2f = sum(flip_before(g2f, i) for i in starts) / max(1, len(starts))
    base_f2g = sum(flip_before(f2g, i) for i in starts) / max(1, len(starts))
    valid = [v for v in fg if v is not None]
    base = {"share_bars_with_greed_to_fear_flip_in_prior_3_days": base_g2f,
            "share_bars_with_fear_to_greed_flip_in_prior_3_days": base_f2g,
            "share_bars_extreme_fear": sum(v < EXTREME_FEAR for v in valid) / len(valid),
            "share_bars_extreme_greed": sum(v > EXTREME_GREED for v in valid) / len(valid),
            "mean_fear_greed": sum(valid) / len(valid)}

    def describe(kind, score, i, n):
        w = [v for v in fg[i:i + WEEK] if v is not None]
        start_v = fg[i]
        before_v = fg[i - WEEK] if i >= WEEK else None
        return {"episode_id": f"{kind}_{n}", "kind": kind,
                "start": times[i].isoformat(), "end": times[i + WEEK - 1].isoformat(),
                "net_return": math.expm1(score),
                "fear_greed_at_start": start_v,
                "fear_greed_change_over_prior_7_days": (start_v - before_v) if (start_v is not None and before_v is not None) else None,
                "greed_to_fear_flip_in_prior_3_days": flip_before(g2f, i),
                "fear_to_greed_flip_in_prior_3_days": flip_before(f2g, i),
                "mean_fear_greed_in_week": (sum(w) / len(w)) if w else None,
                "extreme_fear_share_in_week": (sum(v < EXTREME_FEAR for v in w) / len(w)) if w else None,
                "extreme_greed_share_in_week": (sum(v > EXTREME_GREED for v in w) / len(w)) if w else None}

    worst = [describe("worst_week", s, i, n) for n, (s, i) in enumerate(_windows(rets, k, worst=True), 1)]
    worst_idx = [i for _, i in _windows(rets, k, worst=True)]
    best = [describe("best_week", s, i, n) for n, (s, i) in enumerate(_windows(rets, k, worst=False, exclude=worst_idx), 1)]

    def tally(eps, flag, p0):
        hits = sum(e[flag] for e in eps)
        return {"n_weeks": len(eps), "n_with_flip": hits, "base_rate": p0,
                "binomial_p_value": _binom_tail(hits, len(eps), p0) if eps else None}

    return {"split": "train", "definitions": {"week_bars": WEEK, "lookback_bars": LOOKBACK, "neutral": NEUTRAL,
                                              "extreme_fear_below": EXTREME_FEAR, "extreme_greed_above": EXTREME_GREED,
                                              "weeks_per_side": k},
            "worst_weeks": worst, "best_weeks": best, "train_base_rates": base,
            "worst_weeks_after_greed_to_fear_flip": tally(worst, "greed_to_fear_flip_in_prior_3_days", base_g2f),
            "best_weeks_after_fear_to_greed_flip": tally(best, "fear_to_greed_flip_in_prior_3_days", base_f2g),
            "worst_weeks_after_fear_to_greed_flip": tally(worst, "fear_to_greed_flip_in_prior_3_days", base_f2g),
            "best_weeks_after_greed_to_fear_flip": tally(best, "greed_to_fear_flip_in_prior_3_days", base_g2f),
            "primary_tallies": list(PRIMARY_TALLIES), "moderate_p_threshold": MODERATE_P,
            "note": ("co-occurrence in time, not causation; with 4 weeks per side even 4/4 is weak evidence; only the two "
                     "primary tallies can support 'moderate', at p < 0.05 (Bonferroni over two); the base rate is train-wide")}
