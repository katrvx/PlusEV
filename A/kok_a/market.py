"""Hourly bars.

`synthetic-btcusdt-1h-v1` is a seeded path for tests. The ready run does not
use it; that snapshot is loaded from fixtures by kok_a.snapshot.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

SNAPSHOT_SYNTHETIC = "synthetic-btcusdt-1h-v1"


def synthetic_ohlcv(n: int = 1600, seed: int = 7, symbol: str = "BTCUSDT") -> pd.DataFrame:
    """Hourly spot-like bars. Calm stretches trend; volatile stretches chop.

    Open[t+1] is not equal to close[t]. The fill price is the next open, so a
    close spike is not executable.
    """

    rng = np.random.default_rng(seed)
    calm = np.empty(n, dtype=bool)
    state = True
    for i in range(n):
        if rng.random() < 0.004:
            state = not state
        calm[i] = state
    mu = np.zeros(n)
    i = 0
    while i < n:
        seg = int(rng.integers(48, 160))
        drift = float(rng.choice([-1.0, 1.0]) * rng.uniform(0.0004, 0.0009))
        mu[i : i + seg] = np.where(calm[i : i + seg], drift, 0.0)
        i += seg
    sigma = np.where(calm, 0.0025, 0.01)
    step = mu + sigma * rng.standard_normal(n)
    open_ = 30_000.0 * np.exp(np.cumsum(step))
    close = open_ * np.exp(0.001 * rng.standard_normal(n))
    high = np.maximum(open_, close) * (1 + 0.0005 * rng.random(n))
    low = np.minimum(open_, close) * (1 - 0.0005 * rng.random(n))
    volume = rng.lognormal(mean=5.0, sigma=0.35, size=n)
    start = pd.Timestamp("2023-01-01", tz="UTC")
    return pd.DataFrame(
        {
            "open_time": start + pd.to_timedelta(np.arange(n), unit="h"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "symbol": symbol,
            "venue": "synthetic_spot",
        }
    )


def hash_ohlcv(ohlcv: pd.DataFrame) -> str:
    h = hashlib.sha256()
    times = pd.to_datetime(ohlcv["open_time"], utc=True).astype("int64").to_numpy()
    closes = np.round(ohlcv["close"].to_numpy(dtype=float), 8)
    h.update(times.tobytes())
    h.update(np.ascontiguousarray(closes).tobytes())
    return h.hexdigest()[:16]
