"""Next-bar fill. Costs scale with the change in exposure, not with the signal itself.

The cost is an assumption, not a measured fill: 10 bps, the Binance spot
regular-user taker fee, plus 1 bp of slippage, charged on |Δexposure|.
Spot: no funding.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEE_BPS = 10.0
SLIPPAGE_BPS = 1.0
COST_PER_UNIT = (FEE_BPS + SLIPPAGE_BPS) / 10_000
FEE_SHARE = FEE_BPS / (FEE_BPS + SLIPPAGE_BPS)
ANNUALIZATION = float(np.sqrt(24 * 365))


def simulate(frame: pd.DataFrame, multiplier: pd.Series, visible: np.ndarray | None = None) -> pd.DataFrame:
    """Exposure q = multiplier * target_position.

    `visible` selects rows whose forward returns may be read. Costs depend only
    on the position path, so a train-split score does not have to touch test labels.
    The position path itself is continuous across the visible mask: the first
    bar of a split is charged against the previous bar's exposure.
    """

    q = multiplier.to_numpy(dtype=float) * frame["target_position"].to_numpy(dtype=float)
    previous = np.concatenate([[0.0], q[:-1]])
    turnover = np.abs(q - previous)
    if visible is None:
        visible = np.ones(len(frame), dtype=bool)
    else:
        visible = np.asarray(visible, dtype=bool)
    gross = np.full(len(frame), np.nan)
    idx = np.flatnonzero(visible)
    gross[idx] = q[idx] * frame["ret_next"].to_numpy(dtype=float)[idx]
    cost = COST_PER_UNIT * turnover
    visible_cost = np.where(visible, cost, np.nan)
    return pd.DataFrame(
        {
            "q": q,
            "dq": turnover,
            "dq_signed": q - previous,
            "gross": gross,
            "cost": visible_cost,
            "fees": visible_cost * FEE_SHARE,
            "slippage": visible_cost * (1.0 - FEE_SHARE),
            "net": gross - visible_cost,
            "switch": turnover > 1e-12,
        },
        index=frame.index,
    )


def block_ci(values: np.ndarray, rng: np.random.Generator, block: int = 24, n_boot: int = 200) -> tuple[float, float]:
    """90% interval for the mean, resampling contiguous blocks. NaN if the sample is short."""

    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < block * 2:
        return (float("nan"), float("nan"))
    starts = np.arange(len(x) - block)
    k = len(x) // block
    means = np.empty(n_boot)
    for i in range(n_boot):
        chosen = rng.choice(starts, size=k)
        idx = np.concatenate([np.arange(s, s + block) for s in chosen])
        means[i] = x[idx].mean()
    return float(np.quantile(means, 0.05)), float(np.quantile(means, 0.95))
