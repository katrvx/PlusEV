"""Point-in-time Keep or Kill rule on one kit price path.

Everything here is a pure function of the prices observed so far, so the value
at bar t can only depend on prices[0..t].

raw    : the unchanged frozen demo strategy (A/kok_a/strategies.py, loaded from
         that exact file), long (1.0) or flat (0.0). Warm-up NaN is flat.
gate   : champion `agent::vol_median_05_1` adapted to one path:
         0.5 when realized_vol[t] <= median(realized_vol[t'] for t' < t), else 1.0.
         Full size (1.0) while realized_vol[t] is undefined or no earlier value exists.
target : raw * gate, in {0, 0.5, 1}.

The kit executes only all-in long or flat (integer shares, every buy spends all
cash, every sell closes everything). A 0.5 target therefore cannot be executed;
`kit_long` rounds it DOWN to flat (pre-registered in
eval/challenge/kok-preregistration.md).
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STRATEGY_FILE = ROOT / "A" / "kok_a" / "strategies.py"

# Kit bars are one calendar day apart (generator: start + timedelta(days=i)).
# KoK's realized_vol_7d is 168 hourly log returns = 7 days, so 7 daily returns here.
VOL_WINDOW = 7
HALF, FULL = 0.5, 1.0

STRATEGY_IDS = {
    "trend": "btc-trend-24-72-demo",  # 24-bar vs 72-bar SMA, long when fast > slow
    "mean_reversion": "btc-meanrev-48-demo",  # 48-bar z < -1 enter, z >= 0 exit
}


def _load_frozen():
    # Load the file directly so importing it does not pull in kok_a/__init__ (experiment, LightGBM).
    spec = importlib.util.spec_from_file_location("kok_frozen_strategies", STRATEGY_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_FROZEN = _load_frozen()


def raw_positions(strategy: str, prices) -> np.ndarray:
    """Frozen demo strategy target for every bar; NaN (warm-up / zero std) -> 0.0 flat."""
    _version, pos = _FROZEN.positions(STRATEGY_IDS[strategy], pd.Series(np.asarray(prices, dtype=float)))
    return np.nan_to_num(pos.to_numpy(dtype=float), nan=0.0)


def realized_vol(prices, window: int = VOL_WINDOW) -> np.ndarray:
    """Rolling sample std (ddof=1) of log returns, same formula as kok_a.features.realized_vol_7d."""
    ret = np.log(pd.Series(np.asarray(prices, dtype=float))).diff()
    return ret.rolling(window, min_periods=window).std().to_numpy(dtype=float)


def gate_multipliers(prices, window: int = VOL_WINDOW) -> np.ndarray:
    """0.5 when vol[t] <= expanding median of vol over bars strictly before t, else 1.0."""
    vol = realized_vol(prices, window)
    out = np.full(len(vol), FULL)
    seen: list[float] = []
    for t, v in enumerate(vol):
        if math.isfinite(v):
            if seen and v <= float(np.median(seen)):
                out[t] = HALF
            seen.append(float(v))
    return out


def target_positions(strategy: str, mode: str, prices) -> np.ndarray:
    raw = raw_positions(strategy, prices)
    if mode == "raw":
        return raw
    if mode == "gated":
        return raw * gate_multipliers(prices)
    if mode == "half":  # exposure-only baseline: raw at constant half size
        return raw * HALF
    raise ValueError(f"unknown mode {mode!r}")


def kit_long(target: float) -> bool:
    """All-in kit execution: only a full-size target is held; 0.5 rounds down to flat."""
    return target >= FULL


def kit_action(target: float, shares: int) -> str:
    want = kit_long(target)
    if want and shares == 0:
        return "buy"
    if not want and shares > 0:
        return "sell"
    return "hold"
