"""Point-in-time features and the decision frame built from hourly bars.

A decision is the close of bar t. Features use inputs whose availability time
is at or before that close. The fill is open[t+1]; the position earns the
move from open[t+1] to open[t+2]. Bar t's close is never a fill.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLUMNS = (
    "momentum_24h",
    "momentum_7d",
    "realized_vol_7d",
    "atr_14",
    "price_drawdown",
    "volume_zscore",
    "fear_greed",
    "news_sentiment",
)

MARKET_FEATURES = ("momentum_24h", "momentum_7d", "realized_vol_7d", "atr_14", "price_drawdown", "volume_zscore")


class TemporalLeakError(ValueError):
    """A joined input is timestamped after the decision that would use it."""


def assert_point_in_time(frame: pd.DataFrame) -> None:
    if (frame["data_max_available_at"] > frame["decision_time"]).any():
        raise TemporalLeakError("data_max_available_at is after decision_time")
    for col in ("fear_greed_available_at", "news_available_at"):
        if col not in frame.columns:
            continue
        known = frame[col].notna()
        if known.any() and (frame.loc[known, col] > frame.loc[known, "decision_time"]).any():
            raise TemporalLeakError(f"{col} is after decision_time")


def market_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Lagged price and volume features. Row i uses bars 0..i only."""

    close = ohlcv["close"].astype(float)
    high = ohlcv["high"].astype(float)
    low = ohlcv["low"].astype(float)
    volume = ohlcv["volume"].astype(float)
    log_close = np.log(close)
    ret = log_close.diff()
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    vol_ma = volume.rolling(168, min_periods=168).mean()
    vol_sd = volume.rolling(168, min_periods=168).std()
    peak = close.rolling(168, min_periods=168).max()
    return pd.DataFrame(
        {
            "momentum_24h": log_close - log_close.shift(24),
            "momentum_7d": log_close - log_close.shift(168),
            "realized_vol_7d": ret.rolling(168, min_periods=168).std(),
            "atr_14": true_range.rolling(14, min_periods=14).mean() / close.where(close > 0),
            "price_drawdown": close / peak.where(peak > 0) - 1.0,
            "volume_zscore": (volume.rolling(24, min_periods=24).mean() - vol_ma) / vol_sd.where(vol_sd > 0),
        }
    )


def with_execution(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """One row per bar that has a next open and an open after that."""

    bars = ohlcv.sort_values("open_time").reset_index(drop=True)
    if len(bars) < 3:
        raise ValueError("need at least 3 bars so a decision has a next open and an exit open")
    decision_time = bars["open_time"] + pd.Timedelta(hours=1)
    out = pd.DataFrame(
        {
            "bar_index": np.arange(len(bars) - 2),
            "decision_time": decision_time.iloc[:-2].to_numpy(),
            "open": bars["open"].iloc[:-2].to_numpy(),
            "high": bars["high"].iloc[:-2].to_numpy(),
            "low": bars["low"].iloc[:-2].to_numpy(),
            "close": bars["close"].iloc[:-2].to_numpy(),
            "volume": bars["volume"].iloc[:-2].to_numpy(),
            "fill_open": bars["open"].iloc[1:-1].to_numpy(),
            "exit_open": bars["open"].iloc[2:].to_numpy(),
        }
    )
    out["ret_next"] = out["exit_open"] / out["fill_open"] - 1.0
    out["data_max_available_at"] = out["decision_time"]
    return out


def synthetic_fear_greed(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """A price-derived stand-in used only with the synthetic bars. Not Alternative.me."""

    close_time = pd.to_datetime(ohlcv["open_time"], utc=True) + pd.Timedelta(hours=1)
    daily = ohlcv["close"].groupby(close_time.dt.floor("D")).last()
    change = np.log(daily / daily.shift(7)).fillna(0.0)
    value = (50.0 + 20.0 * np.tanh(change * 5.0)).clip(0.0, 100.0)
    return pd.DataFrame(
        {
            "as_of_day": daily.index,
            "available_at": daily.index + pd.Timedelta(days=1),
            "value": value.to_numpy(dtype=float),
        }
    )


def asof_fear_greed(decision_time: pd.Series, daily: pd.DataFrame) -> pd.DataFrame:
    """Latest reading whose available_at is <= the decision. No fill before publication."""

    left = pd.DataFrame({"decision_time": pd.to_datetime(decision_time, utc=True)}).reset_index()
    left = left.sort_values("decision_time")
    right = daily[["available_at", "value"]].copy()
    right["available_at"] = pd.to_datetime(right["available_at"], utc=True)
    right = right.sort_values("available_at")
    merged = pd.merge_asof(
        left,
        right,
        left_on="decision_time",
        right_on="available_at",
        direction="backward",
    )
    return merged.sort_values("index").reset_index(drop=True)


def asof_news(decision_time: pd.Series, items: pd.DataFrame) -> tuple[np.ndarray, pd.Series]:
    """Mean sentiment of items first seen in (decision-24h, decision]. Absent stays missing."""

    times = pd.to_datetime(decision_time, utc=True)
    clock = times.to_numpy(dtype="datetime64[ns]")
    sentiment = np.full(len(clock), np.nan)
    available = np.empty(len(clock), dtype="datetime64[ns]")
    available[:] = np.datetime64("NaT", "ns")
    if items is not None and len(items):
        seen = pd.to_datetime(items["first_seen_at"], utc=True).to_numpy(dtype="datetime64[ns]")
        values = items["sentiment"].to_numpy(dtype=float)
        order = np.argsort(seen)
        seen, values = seen[order], values[order]
        window = np.timedelta64(24, "h")
        for i, ts in enumerate(clock):
            left = int(np.searchsorted(seen, ts - window, side="left"))
            right = int(np.searchsorted(seen, ts, side="right"))
            if right > left:
                sentiment[i] = float(values[left:right].mean())
                available[i] = seen[right - 1]
    return sentiment, pd.to_datetime(available, utc=True)


def build_frame(
    ohlcv: pd.DataFrame,
    fear_greed: pd.DataFrame | None = None,
    news: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Join execution, market features, lagged fear & greed, and news. Then check the clock.

    News defaults to empty. A missing headline stays missing; nothing is invented
    and nothing is filled across a publication time.
    """

    bars = ohlcv.sort_values("open_time").reset_index(drop=True)
    feat = market_features(bars)
    frame = with_execution(bars)
    idx = frame["bar_index"].to_numpy()
    for col in MARKET_FEATURES:
        frame[col] = feat[col].iloc[idx].to_numpy()
    if fear_greed is None:
        fear_greed = synthetic_fear_greed(bars)
    if news is None:
        news = pd.DataFrame(columns=["first_seen_at", "sentiment"])
    joined = asof_fear_greed(frame["decision_time"], fear_greed)
    frame["fear_greed"] = joined["value"].to_numpy()
    frame["fear_greed_available_at"] = pd.to_datetime(joined["available_at"], utc=True).to_numpy()
    sentiment, available = asof_news(frame["decision_time"], news)
    frame["news_sentiment"] = sentiment
    frame["news_available_at"] = available.to_numpy()
    frame["fear_greed_available_at"] = pd.to_datetime(frame["fear_greed_available_at"], utc=True)
    frame["news_available_at"] = pd.to_datetime(frame["news_available_at"], utc=True)
    frame["decision_time"] = pd.to_datetime(frame["decision_time"], utc=True)
    frame["data_max_available_at"] = pd.to_datetime(frame["data_max_available_at"], utc=True)
    assert_point_in_time(frame)
    return frame


def coverage_table(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    table: dict[str, dict[str, float]] = {}
    for split in ("train", "validation", "test"):
        part = frame[frame["split"] == split]
        table[split] = {name: float(part[name].notna().mean()) if len(part) else float("nan") for name in FEATURE_COLUMNS}
    return table
