"""Transparent gates: the simple rule baseline and the agent's allowlisted threshold gates."""

from __future__ import annotations

import numpy as np
import pandas as pd

ALLOWED_MULTIPLIERS = (0.0, 0.5, 1.0)


def threshold_gate_allocation(spec: dict, context: pd.DataFrame) -> pd.Series:
    """All conditions true -> allocation_when_true, else allocation_when_false.
    Missing feature values are conservative: the row gets min(true, false) allocation,
    whichever direction the gate points."""
    mask = pd.Series(True, index=context.index)
    missing = pd.Series(False, index=context.index)
    for c in spec["conditions"]:
        x = context[c["feature"]]
        if c["op"] == "<=":
            cond = x <= c["threshold"]
        elif c["op"] == ">":
            cond = x > c["threshold"]
        else:
            raise ValueError(f"unknown op {c['op']!r}")
        missing |= x.isna()
        mask &= cond.fillna(False)
    a_t, a_f = float(spec["allocation_when_true"]), float(spec["allocation_when_false"])
    out = np.where(mask, a_t, a_f)
    out = np.where(missing, min(a_t, a_f), out)
    return pd.Series(out, index=context.index, dtype=float)


def rule_gate_spec(train_quantiles: dict[str, dict[float, float]]) -> dict:
    """The simple rule baseline (spec: 'lagged market trend and volatility gate with a
    small fixed parameter set'): full size when 24h momentum is positive and 7d vol is at
    or below its TRAINING median, otherwise half size. Fixed in advance; only the median
    is estimated, on train."""
    return {
        "policy_id": "rule::trend_up_and_vol_below_train_median",
        "family": "threshold_gate",
        "conditions": [
            {"feature": "momentum_24h", "op": ">", "threshold": 0.0},
            {"feature": "realized_vol_7d", "op": "<=", "threshold": float(train_quantiles["realized_vol_7d"][0.5])},
        ],
        "allocation_when_true": 1.0,
        "allocation_when_false": 0.5,
        "thresholds_selected_on": "train",
    }


def allocation(spec: dict, context: pd.DataFrame, lgbm=None) -> pd.Series:
    family = spec["family"]
    if family == "always_on":
        return pd.Series(1.0, index=context.index)
    if family == "cash":
        return pd.Series(0.0, index=context.index)
    if family == "constant":   # benchmark only (exposure-matched); never a candidate, need not be 0, 0.5 or 1
        return pd.Series(min(1.0, max(0.0, float(spec["allocation"]))), index=context.index)
    if family == "threshold_gate":
        return threshold_gate_allocation(spec, context)
    if family == "lgbm_gate":
        if lgbm is None:
            raise ValueError("lgbm_gate needs a fitted LGBMGate")
        return lgbm.allocation(context)
    raise ValueError(f"unknown gate family {family}")


def allocation_mix(alloc: pd.Series, target_position: pd.Series | None = None) -> dict[str, float]:
    """Share of IN-POSITION decisions at each multiplier (bars where the strategy is flat are not gated)."""
    if target_position is not None:
        alloc = alloc[target_position != 0]
    return {str(k): float((alloc == k).mean()) if len(alloc) else 0.0 for k in ALLOWED_MULTIPLIERS}
