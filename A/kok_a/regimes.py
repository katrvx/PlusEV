"""Regime labels and the train-only filter built from them.

Axes are declared once. An axis is skipped when the train column is too
sparse to cut, which is how missing news stays out without a special case.
Cutpoints are fit on train and applied forward. The filter is chosen from
those train buckets only. Validation and the sealed test are not inputs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from kok_a.simulate import block_ci

MIN_AXIS_COVERAGE = 0.90
MIN_BUCKET_BARS = 48


@dataclass(frozen=True)
class Axis:
    name: str
    feature: str
    kind: str
    low: str
    high: str
    mid: str | None = None


AXES: tuple[Axis, ...] = (
    # Two trend windows. The names describe the price path, not whether the strategy should be on.
    Axis("trend_regime", "momentum_24h", "tercile", "bear", "bull", "sideways"),
    Axis("trend_7d_regime", "momentum_7d", "tercile", "bear", "bull", "sideways"),
    Axis("vol_regime", "realized_vol_7d", "median", "low", "high"),
    Axis("vol_change_regime", "vol_ratio_24h_7d", "median", "below_baseline", "above_baseline"),
    # volume_zscore is a traded-volume proxy. It is not a spread or an order-book depth.
    Axis("liquidity_regime", "volume_zscore", "median", "thin", "deep"),
    Axis("sentiment_regime", "fear_greed", "median", "fear", "greed"),
)


def fit_regime_labels(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Cut every covered axis on the train window and label the whole frame."""

    train = frame[frame["split"] == "train"]
    labels = pd.DataFrame(index=frame.index)
    cuts: dict[str, dict] = {}
    active: list[str] = []
    for axis in AXES:
        if axis.feature not in frame.columns:
            continue
        coverage = float(train[axis.feature].notna().mean()) if len(train) else 0.0
        if coverage < MIN_AXIS_COVERAGE:
            continue
        values = frame[axis.feature].to_numpy(dtype=float)
        train_values = train[axis.feature].dropna().to_numpy(dtype=float)
        if axis.kind == "tercile":
            lo, hi = (float(v) for v in np.quantile(train_values, [1.0 / 3.0, 2.0 / 3.0]))
            labels[axis.name] = _tercile(values, lo, hi, axis)
            cuts[axis.name] = {"feature": axis.feature, "kind": "tercile", "edges": [lo, hi]}
        else:
            edge = float(np.median(train_values))
            labels[axis.name] = _median_split(values, edge, axis)
            cuts[axis.name] = {"feature": axis.feature, "kind": "median", "edge": edge}
        active.append(axis.name)
    meta = {"axes": active, "cuts": cuts}
    trend = cuts.get("trend_regime")
    vol = cuts.get("vol_regime")
    if trend is not None:
        meta["momentum_terciles"] = trend["edges"]
    if vol is not None:
        meta["vol_median"] = vol["edge"]
    return labels, meta


def discover_regime_filter(
    frame: pd.DataFrame,
    simulated: pd.DataFrame,
    seed: int,
    n_boot: int,
) -> dict:
    """Flat where the train interval is entirely below zero. Full size where it is entirely above.

    A bucket needs enough bars for the block bootstrap. Buckets that still
    contain zero are left alone. With no such bucket the filter stays fully on.

    The returned spec is `runner.regime_spec`. Lane B may treat it as a competitor.
    The keys are stable: policy_id, family, flat_buckets, full_buckets,
    allocation_flat, allocation_full, allocation_else, selected_on, summary.
    Each bucket entry is {"axis", "bucket"}.
    """

    train = frame["split"] == "train"
    flat: list[dict[str, str]] = []
    full: list[dict[str, str]] = []
    for axis in AXES:
        if axis.name not in frame.columns:
            continue
        for bucket in sorted(str(v) for v in frame.loc[train, axis.name].dropna().unique()):
            mask = train & (frame[axis.name] == bucket)
            net = simulated.loc[mask, "net"].to_numpy(dtype=float)
            net = net[np.isfinite(net)]
            if len(net) < MIN_BUCKET_BARS:
                continue
            lo, hi = block_ci(net, _rng(seed, axis.name, bucket), n_boot=n_boot)
            if not (np.isfinite(lo) and np.isfinite(hi)):
                continue
            entry = {"axis": axis.name, "bucket": bucket}
            if hi < 0:
                flat.append(entry)
            elif lo > 0:
                full.append(entry)
    else_alloc = 1.0 if not flat and not full else (0.5 if flat and full else (0.0 if full else 1.0))
    return {
        "policy_id": "rule::regime_filter",
        "family": "regime_gate",
        "flat_buckets": flat,
        "full_buckets": full,
        "allocation_flat": 0.0,
        "allocation_full": 1.0,
        "allocation_else": else_alloc,
        "selected_on": "train",
        "summary": _summary(flat, full, else_alloc),
    }


def _summary(flat: list[dict[str, str]], full: list[dict[str, str]], else_alloc: float) -> str:
    if not flat and not full:
        return "No train regime had an interval entirely off zero, so the filter leaves the strategy on."
    parts = []
    if flat:
        parts.append("flat in " + ", ".join(f"{item['axis']}={item['bucket']}" for item in flat))
    if full:
        parts.append("full size in " + ", ".join(f"{item['axis']}={item['bucket']}" for item in full))
    parts.append(f"allocation {else_alloc:g} in the remaining regimes")
    return "Train intervals only: " + "; ".join(parts) + "."


def _tercile(values: np.ndarray, lo: float, hi: float, axis: Axis) -> np.ndarray:
    out = np.array([None] * len(values), dtype=object)
    known = np.isfinite(values)
    out[known & (values < lo)] = axis.low
    out[known & (values > hi)] = axis.high
    out[known & (values >= lo) & (values <= hi)] = axis.mid
    return out


def _median_split(values: np.ndarray, edge: float, axis: Axis) -> np.ndarray:
    out = np.array([None] * len(values), dtype=object)
    known = np.isfinite(values)
    out[known & (values > edge)] = axis.high
    out[known & (values <= edge)] = axis.low
    return out


def _rng(seed: int, *parts: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{seed}|{'|'.join(parts)}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))
