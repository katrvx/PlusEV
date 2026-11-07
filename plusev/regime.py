"""Regime labels computed from price only, using data available at bar t (no look-ahead).

The organisers' hidden test gives prices only (no real dates, no volume, no symbol),
so every feature here is price-derived. Windows are short because kit paths can be
as short as 12 (synthetic) or 48 (real) bars.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

WARMUP = 10          # bars needed before a regime exists
VOL_WINDOW = 10      # bars of log returns for realised volatility
SHOCK_WINDOW = 3     # short window for the volatility-shock ratio
SHOCK_RATIO = 1.8    # short vol / long vol above this = "shock"
TREND_Z = 0.5        # trend strength (in vol units) above this = up/down

FEATURES = {
    "vol": ("low", "mid", "high"),
    "shock": ("calm", "shock"),
    "trend": ("up", "down", "chop"),
}


def _log_returns(prices: list[int]) -> list[float]:
    return [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def raw_features(prices: list[int], t: int) -> dict | None:
    """Continuous features at bar t, from prices[0..t] only. None during warm-up."""
    if t < WARMUP:
        return None
    window = prices[max(0, t - VOL_WINDOW) : t + 1]
    rets = _log_returns(window)
    vol = _std(rets)
    short = _std(rets[-SHOCK_WINDOW:])
    shock_ratio = short / vol if vol > 0 else 1.0
    move = math.log(prices[t] / prices[t - VOL_WINDOW + 1])
    trend_z = move / (vol * math.sqrt(VOL_WINDOW - 1)) if vol > 0 else 0.0
    return {"vol": vol, "shock_ratio": shock_ratio, "trend_z": trend_z}


def label(raw: dict, thresholds: dict) -> dict:
    lo, hi = thresholds["vol_terciles"]
    vol = "low" if raw["vol"] <= lo else "high" if raw["vol"] > hi else "mid"
    shock = "shock" if raw["shock_ratio"] > SHOCK_RATIO else "calm"
    z = raw["trend_z"]
    trend = "up" if z > TREND_Z else "down" if z < -TREND_Z else "chop"
    return {"vol": vol, "shock": shock, "trend": trend}


def regime_at(prices: list[int], t: int, thresholds: dict) -> dict | None:
    raw = raw_features(prices, t)
    return None if raw is None else label(raw, thresholds)


def fit_thresholds(paths: list[list[int]]) -> dict:
    """Volatility terciles from TRAINING paths only, then frozen."""
    vols = sorted(
        f["vol"]
        for prices in paths
        for t in range(WARMUP, len(prices))
        if (f := raw_features(prices, t)) is not None
    )
    if not vols:
        raise ValueError("No bars past warm-up in training paths")
    return {
        "vol_terciles": [vols[len(vols) // 3], vols[2 * len(vols) // 3]],
        "warmup": WARMUP,
        "fitted_on_bars": len(vols),
    }


def save(thresholds: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(thresholds, indent=2))


def load(path: Path) -> dict:
    return json.loads(path.read_text())
