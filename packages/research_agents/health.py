"""Bad luck vs broken (spec section 8): is the unchanged strategy's validation result a plausible draw
from its training behaviour, and if not, which ASSUMPTION changed?

Code, not an agent, computes this. It reads validation, so only the critic (and the report) sees it;
the diagnostic analyst and the gate proposer stay train-only.

Inputs come from Lane A's development view:
- exp.train_predictive_range: 5th..95th percentile of compounded net return over a 14-day (336-bar)
  path, block-bootstrapped from TRAIN returns only;
- exp.equity: per-bar always-on net return and exposure for train and validation;
- exp.baselines / exp.costs / exp.per_regime: turnover, fees, regime counts per split.

Pre-registered rules (fixed before any run, never tuned on results):
- validation is cut into non-overlapping 14-day blocks; under the training distribution about 5% of
  blocks fall below the range and 5% above; more than chance (one-sided binomial p < 0.05) means the
  results are OUTSIDE the training range;
- an assumption has changed if a train->validation ratio (exposure, turnover per bar, cost per bar,
  bar volatility) leaves [2/3, 3/2], or a regime axis's bucket shares move by total variation >= 0.25.
A poor result alone is never called a breakdown.
"""

from __future__ import annotations

import math

TAIL = 0.05            # each side of Lane A's 90% range
P_ALERT = 0.05         # one-sided binomial threshold for "more blocks outside than chance"
RATIO_BAND = (2 / 3, 3 / 2)
TV_ALERT = 0.25

# which regime axis describes the distribution of a gate feature (for the critic)
FEATURE_AXIS = {"fear_greed": "sentiment_regime", "news_sentiment": "sentiment_regime",
                "realized_vol_7d": "vol_regime", "atr_14": "vol_regime",
                "momentum_24h": "trend_regime", "momentum_7d": "trend_regime", "price_drawdown": "trend_regime",
                "volume_zscore": "liquidity_regime"}


def _binom_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    return float(sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def _compound(xs) -> float:
    out = 1.0
    for x in xs:
        out *= 1.0 + x
    return out - 1.0


def _std(xs) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def _ratio(a, b):
    return (b / a) if (a and math.isfinite(a) and math.isfinite(b)) else None


def strategy_health(exp) -> dict | None:
    """None when the loader gives no train range or no per-bar equity (e.g. the synthetic stand-in)."""
    rng = getattr(exp, "train_predictive_range", None)
    equity = getattr(exp, "equity", None) or []
    if rng is None or not equity:
        return None
    low, high, horizon = float(rng.low), float(rng.high), int(rng.horizon_bars)
    bars = {s: [p for p in equity if p.split == s] for s in ("train", "validation")}
    if not bars["train"] or len(bars["validation"]) < horizon:
        return None
    net = {s: [float(p.net_return) for p in v] for s, v in bars.items()}

    blocks = []
    for i in range(0, len(net["validation"]) - horizon + 1, horizon):
        r = _compound(net["validation"][i:i + horizon])
        blocks.append({"start": bars["validation"][i].decision_time.isoformat(), "net_return": r,
                       "position": "below" if r < low else "above" if r > high else "inside"})
    n = len(blocks)
    n_below = sum(b["position"] == "below" for b in blocks)
    n_above = sum(b["position"] == "above" for b in blocks)
    p_below, p_above = _binom_tail(n_below, n, TAIL), _binom_tail(n_above, n, TAIL)
    outside = p_below < P_ALERT or p_above < P_ALERT

    # assumptions: train vs validation
    base = {b.split: b.metrics for b in getattr(exp, "baselines", []) if b.policy == "always_on"}
    cost = {c.split: c for c in getattr(exp, "costs", [])}
    nb = {s: len(v) for s, v in bars.items()}
    checks = []

    def ratio_check(name, a, b, note):
        r = _ratio(a, b)
        if r is None:
            return
        changed = not (RATIO_BAND[0] <= r <= RATIO_BAND[1])
        checks.append({"assumption": name, "train": a, "validation": b, "ratio": r, "changed": changed, "note": note})

    if "train" in base and "validation" in base:
        ratio_check("exposure", base["train"].exposure, base["validation"].exposure, "mean |position|")
        ratio_check("turnover_per_bar", base["train"].turnover / nb["train"], base["validation"].turnover / nb["validation"],
                    "how often the strategy trades")
    if "train" in cost and "validation" in cost:
        ratio_check("cost_per_bar", (cost["train"].fees + cost["train"].slippage) / nb["train"],
                    (cost["validation"].fees + cost["validation"].slippage) / nb["validation"], "fees + slippage per bar")
    ratio_check("bar_volatility", _std(net["train"]), _std(net["validation"]), "std of per-bar net return")

    for axis in sorted({r.regime_feature for r in getattr(exp, "per_regime", [])}):
        cnt = {s: {r.bucket: r.n_decisions for r in exp.per_regime if r.regime_feature == axis and r.split == s}
               for s in ("train", "validation")}
        if not all(sum(v.values()) for v in cnt.values()):
            continue
        share = {s: {k: v / sum(c.values()) for k, v in c.items()} for s, c in cnt.items()}
        keys = sorted(set(share["train"]) | set(share["validation"]))
        tv = 0.5 * sum(abs(share["train"].get(k, 0.0) - share["validation"].get(k, 0.0)) for k in keys)
        checks.append({"assumption": f"{axis}_shares", "train": share["train"], "validation": share["validation"],
                       "total_variation": tv, "changed": tv >= TV_ALERT, "note": "how often each regime occurs"})

    changed = [c["assumption"] for c in checks if c["changed"]]
    status = "outside_training_range" if outside else "within_training_range"
    if outside:
        side = "below" if p_below < P_ALERT else "above"
        head = (f"{n_below if side == 'below' else n_above} of {n} validation 14-day blocks fall {side} the training range, "
                f"more than chance: performance differs from training.")
    else:
        head = (f"{n - n_below - n_above} of {n} validation 14-day blocks fall inside the training range "
                f"[{low:+.4f}, {high:+.4f}]: a loss alone does not show the strategy broke.")
    tail = (" Assumptions that changed: " + ", ".join(changed) + ".") if changed else " No tracked assumption changed."
    return {
        "status": status, "summary": head + tail, "changed_assumptions": changed,
        "train_range": {"low": low, "high": high, "horizon_bars": horizon, "source": "Lane A, train returns only"},
        "validation_blocks": blocks, "n_blocks": n, "n_below": n_below, "n_above": n_above,
        "p_below": p_below, "p_above": p_above, "validation_net_return": _compound(net["validation"]),
        "checks": checks,
        "rules": {"tail_each_side": TAIL, "p_alert": P_ALERT, "ratio_band": list(RATIO_BAND), "tv_alert": TV_ALERT},
    }


def feature_shift(health: dict | None, features: list[str]) -> list[str]:
    """Changed regime axes that describe the given gate features (for critiques)."""
    if not health:
        return []
    axes = {FEATURE_AXIS[f] for f in features if f in FEATURE_AXIS}
    return [a for a in health["changed_assumptions"] if a.removesuffix("_shares") in axes]
