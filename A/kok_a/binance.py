"""Binance spot kline ingestion.

Spot, not futures: the demo strategies do not model funding. Archive files
changed open-time units to microseconds in 2025; both units are normalised
to UTC milliseconds before anything else sees them.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

KLINE_COLUMNS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore",
)


def normalize_binance_epoch(value: int | float) -> int:
    """Return the timestamp in milliseconds."""

    v = int(value)
    if v >= 10**15:  # microseconds (spot archive, 2025+)
        return v // 1000
    if v >= 10**12:  # milliseconds
        return v
    if v >= 10**9:  # seconds
        return v * 1000
    raise ValueError(f"unrecognised Binance timestamp: {value}")


def binance_vision_monthly_url(symbol: str = "BTCUSDT", interval: str = "1h", year: int = 2024, month: int = 1) -> str:
    return (
        "https://data.binance.vision/data/spot/monthly/klines/"
        f"{symbol}/{interval}/{symbol}-{interval}-{year}-{month:02d}.zip"
    )


def read_binance_klines(path: str | Path, symbol: str = "BTCUSDT") -> pd.DataFrame:
    """Read a Binance kline CSV (headerless archive file, or a headed export)."""

    path = Path(path)
    peek = pd.read_csv(path, header=None, nrows=1)
    if _is_number(peek.iloc[0, 0]):
        raw = pd.read_csv(path, header=None)
        raw.columns = list(KLINE_COLUMNS[: raw.shape[1]])
    else:
        raw = pd.read_csv(path)
        raw.columns = [str(c).strip().lower() for c in raw.columns]
    missing = [c for c in ("open_time", "open", "high", "low", "close", "volume") if c not in raw.columns]
    if missing:
        raise ValueError(f"{path} is missing kline columns {missing}")
    open_ms = raw["open_time"].map(normalize_binance_epoch).astype("int64")
    out = pd.DataFrame(
        {
            "open_time": pd.to_datetime(open_ms, unit="ms", utc=True),
            "open": raw["open"].astype(float),
            "high": raw["high"].astype(float),
            "low": raw["low"].astype(float),
            "close": raw["close"].astype(float),
            "volume": raw["volume"].astype(float),
            "symbol": symbol,
            "venue": "binance_spot",
        }
    )
    if (out["close"] <= 0).any() or (out["open"] <= 0).any():
        raise ValueError(f"{path} has a non-positive price")
    return out.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)


def _is_number(value: object) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True
