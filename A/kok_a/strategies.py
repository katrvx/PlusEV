"""Frozen demo strategies. They are labelled fixtures, not discovered alpha.

Each function sees the close series only through the current bar. The returned
position is the strategy's target; a gate multiplies it and does not edit it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def positions(strategy_id: str, close: pd.Series) -> tuple[str, pd.Series]:
    found = STRATEGIES.get(strategy_id)
    if found is None:
        raise KeyError(f"unknown strategy {strategy_id}; known: {tuple(STRATEGIES)}")
    version, generate = found
    return version, generate(close)


def _trend(close: pd.Series) -> pd.Series:
    """Long when the 24-bar average is above the 72-bar average, else flat."""

    fast = close.rolling(24, min_periods=24).mean()
    slow = close.rolling(72, min_periods=72).mean()
    ready = fast.notna() & slow.notna()
    out = pd.Series(np.nan, index=close.index, dtype=float)
    out.loc[ready] = (fast.loc[ready] > slow.loc[ready]).astype(float)
    return out


def _mean_reversion(close: pd.Series) -> pd.Series:
    """Enter when the 48-bar z-score is below -1; exit when it returns to 0."""

    mean = close.rolling(48, min_periods=48).mean()
    std = close.rolling(48, min_periods=48).std()
    z = (close - mean) / std.where(std > 0)
    holding = 0.0
    out = np.empty(len(close), dtype=float)
    for i, zi in enumerate(z.to_numpy()):
        if not np.isfinite(zi):
            out[i] = np.nan
            continue
        if holding == 0.0 and zi < -1.0:
            holding = 1.0
        elif holding == 1.0 and zi >= 0.0:
            holding = 0.0
        out[i] = holding
    return pd.Series(out, index=close.index)


STRATEGIES = {
    "btc-trend-24-72-demo": ("trend-sma-24-72-v1", _trend),
    "btc-meanrev-48-demo": ("meanrev-z48-v1", _mean_reversion),
}
