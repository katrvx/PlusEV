"""Transparent gates: the simple rule baseline and the agent's allowlisted threshold gates."""

from __future__ import annotations

import numpy as np
import pandas as pd

ALLOWED_MULTIPLIERS = (0.0, 0.5, 1.0)


def threshold_gate_allocation(spec: dict, context: pd.DataFrame) -> pd.Series:
    """All conditions true -> allocation_when_true, else allocation_when_false.
    Missing feature values are treated conservatively: condition is False."""
    mask = pd.Series(True, index=context.index)
    for c in spec["conditions"]:
        x = context[c["feature"]]
        cond = (x <= c["threshold"]) if c["op"] == "<=" else (x > c["threshold"])
        mask &= cond.fillna(False)
    out = np.where(mask, spec["allocation_when_true"], spec["allocation_when_false"])
    return pd.Series(out, index=context.index, dtype=float)


def rule_gate_spec(train_context: pd.DataFrame) -> dict:
    """The simple rule baseline (spec: 'lagged market trend and volatility gate with a
    small fixed parameter set'): full size when 24h momentum is positive and 7d vol is
    below its training median, otherwise half size. Parameters fixed in advance; only
    the median is estimated, on TRAIN only."""
    vol_median = float(train_context["realized_vol_7d"].median())
    return {
        "policy_id": "rule::trend_up_and_vol_below_train_median",
        "family": "threshold_gate",
        "conditions": [
            {"feature": "momentum_24h", "op": ">", "threshold": 0.0},
            {"feature": "realized_vol_7d", "op": "<=", "threshold": vol_median},
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
    if family == "threshold_gate":
        return threshold_gate_allocation(spec, context)
    if family == "lgbm_gate":
        if lgbm is None:
            raise ValueError("lgbm_gate needs a fitted LGBMGate")
        return lgbm.allocation(context)
    raise ValueError(f"unknown gate family {family}")
