"""Allowlisted allocation multipliers. Missing feature values fail the condition (flat, not filled)."""

from __future__ import annotations

import numpy as np
import pandas as pd

ALLOWED_MULTIPLIERS = (0.0, 0.5, 1.0)


def threshold_gate_allocation(spec: dict, context: pd.DataFrame) -> pd.Series:
    mask = pd.Series(True, index=context.index)
    for condition in spec["conditions"]:
        column = context[condition["feature"]]
        if condition["op"] == "<=":
            passed = column <= condition["threshold"]
        elif condition["op"] == ">":
            passed = column > condition["threshold"]
        else:
            raise ValueError(f"unsupported comparison {condition['op']}")
        mask &= passed.fillna(False)
    true_alloc = float(spec["allocation_when_true"])
    false_alloc = float(spec["allocation_when_false"])
    _check_multiplier(true_alloc)
    _check_multiplier(false_alloc)
    return pd.Series(np.where(mask, true_alloc, false_alloc), index=context.index, dtype=float)


def rule_gate_spec(train_context: pd.DataFrame) -> dict:
    """Full size only when 24h momentum is positive and 7d vol is at or below the train median.

    The median is the only fitted number, and it is fitted on train. The rule
    itself is fixed in advance: those conditions get 1, every other bar gets 0.
    A rule that cannot go flat cannot answer "switch this strategy off".
    """

    vol_median = float(train_context["realized_vol_7d"].median())
    return {
        "policy_id": "rule::trend_up_and_vol_below_train_median",
        "family": "threshold_gate",
        "conditions": [
            {"feature": "momentum_24h", "op": ">", "threshold": 0.0},
            {"feature": "realized_vol_7d", "op": "<=", "threshold": vol_median},
        ],
        "allocation_when_true": 1.0,
        "allocation_when_false": 0.0,
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


def _check_multiplier(value: float) -> None:
    if value not in ALLOWED_MULTIPLIERS:
        raise ValueError(f"allocation {value} is not in {ALLOWED_MULTIPLIERS}")
