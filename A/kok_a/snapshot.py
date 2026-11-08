"""Frozen inputs for the ready run, and the downloader that builds them.

The ready snapshot is Binance spot BTCUSDT 1h plus the Alternative.me Fear &
Greed index. News is not in it: there is no first-seen archive here, so the
column stays missing instead of being invented. The synthetic price path
remains for tests that need a spike or a fixed seed.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pandas as pd

from kok_a.binance import read_binance_klines
from kok_a.market import SNAPSHOT_SYNTHETIC, hash_ohlcv, synthetic_ohlcv

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures"
OHLCV_PATH = FIXTURE_DIR / "btcusdt_1h_spot.csv"
FIVE_MIN_PATH = FIXTURE_DIR / "btcusdt_5m_spot.csv"
FIVE_MIN_MANIFEST_PATH = FIXTURE_DIR / "snapshot_5m.json"
FEAR_GREED_PATH = FIXTURE_DIR / "fear_greed.csv"
MANIFEST_PATH = FIXTURE_DIR / "snapshot.json"

SNAPSHOT_READY = "binance-spot-btcusdt-1h-201802-202610"
READY_START = pd.Timestamp("2018-02-01", tz="UTC")
READY_END = pd.Timestamp("2026-11-01", tz="UTC")  # exclusive; last open is 2026-10-31 23:00
WINDOW_LABEL = "2018-02-01 through 2026-10-31"
FIVE_MIN_START = pd.Timestamp("2026-05-08", tz="UTC")
FIVE_MIN_END = pd.Timestamp("2026-11-08", tz="UTC")  # exclusive; last open is 2026-11-07 23:55

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
FNG_URL = "https://api.alternative.me/fng/?limit=0&format=json"
FNG_ATTRIBUTION = "Alternative.me Crypto Fear & Greed Index"


def load_inputs(dataset_snapshot_id: str, n: int = 1600, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Return bars, a fear-and-greed table, and a provenance map."""

    if dataset_snapshot_id == SNAPSHOT_SYNTHETIC:
        ohlcv = synthetic_ohlcv(n=n, seed=seed)
        from kok_a.features import synthetic_fear_greed

        return ohlcv, synthetic_fear_greed(ohlcv), _synthetic_provenance()
    if dataset_snapshot_id == SNAPSHOT_READY:
        return read_binance_klines(OHLCV_PATH), read_fear_greed(FEAR_GREED_PATH), _ready_provenance()
    ohlcv = read_binance_klines(dataset_snapshot_id)
    provenance = _ready_provenance()
    provenance["prices"] = f"binance_spot_csv:{dataset_snapshot_id}"
    provenance["fear_greed"] = "not_joined"
    empty = pd.DataFrame(columns=["available_at", "value"])
    return ohlcv, empty, provenance


def read_fear_greed(path: Path = FEAR_GREED_PATH) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["available_at"] = pd.to_datetime(frame["available_at"], utc=True)
    frame["as_of_day"] = pd.to_datetime(frame["as_of_day"], utc=True)
    frame["value"] = frame["value"].astype(float)
    return frame.sort_values("available_at").reset_index(drop=True)


def fetch_ready_snapshot() -> dict:
    """Download the public series and write the fixture files. Safe to re-run."""

    FIXTURE_DIR.mkdir(exist_ok=True)
    ohlcv = _fetch_klines(READY_START, READY_END)
    fear = _fetch_fear_greed(READY_START - pd.Timedelta(days=3), READY_END)
    _write_ohlcv(ohlcv, OHLCV_PATH)
    fear.to_csv(FEAR_GREED_PATH, index=False)
    loaded = read_binance_klines(OHLCV_PATH)
    gaps = _gap_count(loaded)
    manifest = {
        "id": SNAPSHOT_READY,
        "symbol": "BTCUSDT",
        "venue": "binance_spot",
        "interval": "1h",
        "start": READY_START.isoformat(),
        "end_exclusive": READY_END.isoformat(),
        "n_bars": int(len(loaded)),
        "n_gaps_over_1h": gaps,
        "market_hash": hash_ohlcv(loaded),
        "first_open": float(loaded["open"].iloc[0]),
        "last_close": float(loaded["close"].iloc[-1]),
        "fear_greed_rows": int(len(fear)),
        "sources": {
            "ohlcv": BINANCE_KLINES,
            "fear_greed": "https://api.alternative.me/fng/",
        },
        "fear_greed_attribution": FNG_ATTRIBUTION,
        "fear_greed_availability": "index timestamp plus 24 hours; historical publication time is not documented",
        "news": "omitted",
        "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def fetch_five_minute_snapshot() -> dict:
    """BTCUSDT 5m for the six months ending 2026-11-08. Not the sealed-test snapshot."""

    FIXTURE_DIR.mkdir(exist_ok=True)
    raw = _fetch_klines(FIVE_MIN_START, FIVE_MIN_END, interval="5m")
    _write_ohlcv(raw, FIVE_MIN_PATH)
    loaded = read_binance_klines(FIVE_MIN_PATH)
    gaps = _gap_count(loaded, pd.Timedelta(minutes=5))
    manifest = {
        "id": "binance-spot-btcusdt-5m-202605-202611",
        "symbol": "BTCUSDT",
        "venue": "binance_spot",
        "interval": "5m",
        "start": FIVE_MIN_START.isoformat(),
        "end_exclusive": FIVE_MIN_END.isoformat(),
        "n_bars": int(len(loaded)),
        "n_gaps_over_5m": gaps,
        "market_hash": hash_ohlcv(loaded),
        "first_open": float(loaded["open"].iloc[0]),
        "last_close": float(loaded["close"].iloc[-1]),
        "sources": {"ohlcv": BINANCE_KLINES},
        "note": "Visual series only. The sealed test stays on the hourly snapshot. 24/72 and 48 are hourly bar counts.",
        "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    FIVE_MIN_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _fetch_klines(start: pd.Timestamp, end: pd.Timestamp, symbol: str = "BTCUSDT", interval: str = "1h") -> pd.DataFrame:
    step_ms = {"1h": 3_600_000, "5m": 300_000}[interval]
    cursor = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    rows: list[list] = []
    while cursor < end_ms:
        url = f"{BINANCE_KLINES}?symbol={symbol}&interval={interval}&startTime={cursor}&endTime={end_ms - 1}&limit=1000"
        batch = _get_json(url)
        if not batch:
            break
        rows.extend(batch)
        nxt = int(batch[-1][0]) + step_ms
        if nxt <= cursor:
            break
        cursor = nxt
        if len(batch) < 1000:
            break
    if not rows:
        raise RuntimeError("Binance returned no klines")
    frame = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "count", "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    frame = frame.drop_duplicates("open_time").sort_values("open_time")
    frame = frame[(frame["open_time"].astype("int64") >= int(start.timestamp() * 1000))]
    frame = frame[(frame["open_time"].astype("int64") < end_ms)]
    return frame.reset_index(drop=True)


def _write_ohlcv(raw: pd.DataFrame, path: Path) -> None:
    raw[["open_time", "open", "high", "low", "close", "volume"]].to_csv(path, index=False)


def _fetch_fear_greed(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    payload = _get_json(FNG_URL)
    records = []
    for item in payload["data"]:
        as_of = pd.to_datetime(int(item["timestamp"]), unit="s", utc=True)
        if as_of < start or as_of >= end:
            continue
        records.append(
            {
                "as_of_day": as_of.isoformat(),
                "available_at": (as_of + pd.Timedelta(days=1)).isoformat(),
                "value": float(item["value"]),
                "classification": item.get("value_classification", ""),
                "source": FNG_ATTRIBUTION,
            }
        )
    if not records:
        raise RuntimeError("Alternative.me returned no Fear & Greed rows for the window")
    return pd.DataFrame(records).sort_values("available_at").reset_index(drop=True)


def _gap_count(ohlcv: pd.DataFrame, step: pd.Timedelta = pd.Timedelta(hours=1)) -> int:
    delta = pd.to_datetime(ohlcv["open_time"], utc=True).diff().dropna()
    return int((delta > step).sum())


def _get_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "keep-or-kill-lane-a/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def _synthetic_provenance() -> dict[str, str]:
    return {
        "prices": "synthetic",
        "fear_greed": "synthetic_from_price",
        "news": "omitted",
        "strategies": "demo_generator",
        "costs": "assumed",
        "metrics": "computed",
    }


def _ready_provenance() -> dict[str, str]:
    return {
        "prices": "binance_spot_btcusdt_1h",
        "fear_greed": "alternative.me, available the next UTC day",
        "news": "omitted",
        "strategies": "demo_generator",
        "costs": "assumed_binance_spot_taker_10bps_plus_1bp_slippage",
        "metrics": "computed",
    }
