"""STAND-IN for Lane A, so Lane B can be built and tested today. Replace with Lane A's
`run_experiment` / GateRunner as soon as it exists; the interface is identical.

Clearly synthetic (labelled everywhere; the regime structure is planted on purpose): hourly bars where trends persist in calm markets
and chop dominates in volatile ones, plus a frozen 24h-momentum strategy. Execution is
next-bar with per-unit switching cost, as the spec requires: decision at bar t uses
features known at t, exposure earns the t -> t+1 return, cost c * |q_t - q_{t-1}|.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from packages.contracts_lane_b import (
    BaselineRow, CostBreakdown, ExperimentResult, GateEvaluation, Metrics, RegimeRow, Window,
)
from packages.meta_policy import LGBMGate, allocation, rule_gate_spec

COST_PER_UNIT = 0.0006       # 6 bp per unit of exposure change (fees + slippage)
FEE_SHARE = 0.6              # of which fees; rest slippage
START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def make_market(n: int = 7000, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    calm = np.empty(n, dtype=bool)
    state = True
    for i in range(n):                       # persistent vol regime (Markov)
        if rng.random() < (1 / 250 if state else 1 / 250):
            state = not state
        calm[i] = state
    mu = np.zeros(n)
    i = 0
    while i < n:                             # trend segments only in calm regime
        seg = int(rng.integers(60, 240))
        drift = rng.choice([-1, 1]) * rng.uniform(0.0005, 0.0010)
        mu[i:i + seg] = np.where(calm[i:i + seg], drift, 0.0)
        i += seg
    sigma = np.where(calm, 0.003, 0.012)
    r = mu + sigma * rng.standard_normal(n)
    chop = (~calm) & (np.arange(n) > 0)
    r[chop] -= 0.3 * np.roll(r, 1)[chop]    # mean reversion in volatile chop
    price = 30000 * np.exp(np.cumsum(r))
    ts = [START + timedelta(hours=k) for k in range(n)]
    simple = np.expm1(r)                     # simulator works in simple returns (one convention everywhere)
    df = pd.DataFrame({"decision_time": ts, "close": price, "ret_next": np.append(simple[1:], np.nan)})
    logp = np.log(price)
    df["momentum_24h"] = pd.Series(logp).diff(24).values
    df["realized_vol_7d"] = pd.Series(r).rolling(168).std().values
    df["volume_zscore"] = (pd.Series(np.abs(r)).rolling(24).mean() / pd.Series(np.abs(r)).rolling(500).mean() - 1).values \
        + 0.3 * rng.standard_normal(n)
    daily = pd.Series(50 + 20 * np.tanh(pd.Series(logp).diff(24 * 7).values * 10)).iloc[::24]
    df["fear_greed"] = daily.reindex(range(n)).ffill().shift(24).values      # next-day availability rule
    df["news_sentiment"] = np.where(rng.random(n) < 0.3, rng.uniform(-1, 1, n), np.nan)   # sparse coverage
    df["data_max_available_at"] = df["decision_time"]
    df["target_position"] = (df["momentum_24h"] > 0).astype(float)                         # frozen strategy
    df = df.iloc[200:-1].reset_index(drop=True)
    n2 = len(df)
    df["split"] = np.where(np.arange(n2) < 0.6 * n2, "train", np.where(np.arange(n2) < 0.8 * n2, "validation", "test"))
    return df


def simulate(df: pd.DataFrame, mult: pd.Series) -> pd.DataFrame:
    """Next-bar execution: exposure q_t (decided at t) earns the simple return t -> t+1;
    every change in exposure costs COST_PER_UNIT * |q_t - q_{t-1}| (fees + slippage)."""
    q = mult.values * df["target_position"].values
    dq = np.abs(np.diff(np.concatenate([[0.0], q])))
    gross = q * df["ret_next"].values
    cost = COST_PER_UNIT * dq
    return pd.DataFrame({"q": q, "gross": gross, "cost": cost, "net": gross - cost, "switch": dq > 0}, index=df.index)


def _rng_for(*parts) -> np.random.Generator:
    """Deterministic: same inputs -> same bootstrap draws -> same CI and evidence id."""
    return np.random.default_rng(int(hashlib.sha256(repr(parts).encode()).hexdigest()[:12], 16))


def _block_indices(n: int, rng, block: int = 48) -> np.ndarray:
    starts = rng.integers(0, n - block + 1, size=n // block + 1)
    return np.concatenate([np.arange(s, s + block) for s in starts])[:n]


def _compound(x: np.ndarray) -> float:
    return float(np.prod(1 + x) - 1)


def _boot_ci(series: list[np.ndarray], stat, rng, n_boot: int = 600, block: int = 48) -> tuple[float, float]:
    """Moving-block bootstrap; all series are resampled with the SAME indices (paired)."""
    n = len(series[0])
    if n < block * 2:
        return (float("nan"), float("nan"))
    vals = []
    for _ in range(n_boot):
        idx = _block_indices(n, rng, block)
        vals.append(stat(*[s[idx] for s in series]))
    return float(np.quantile(vals, .05)), float(np.quantile(vals, .95))


def metrics(sim: pd.DataFrame, rng) -> Metrics:
    net = sim["net"].values
    eq = np.cumprod(1 + net)
    mdd = float(np.max(1 - eq / np.maximum.accumulate(eq))) if len(eq) else 0.0
    sd = net.std()
    down = net[net < 0].std() if (net < 0).any() else np.nan
    ann = np.sqrt(24 * 365)
    return Metrics(net_return=_compound(net), sharpe=float(net.mean() / sd * ann) if sd > 0 else None,
                   sortino=float(net.mean() / down * ann) if down and down > 0 else None, max_drawdown=mdd,
                   turnover=float(np.abs(np.diff(np.concatenate([[0], sim["q"].values]))).sum()),
                   n_switches=int(sim["switch"].sum()), exposure=float(sim["q"].mean()),
                   ci_net_return=_boot_ci([net], _compound, rng))


def regime_labels(df: pd.DataFrame, train: pd.DataFrame) -> pd.DataFrame:
    """Uses the same quantiles as the agents' threshold grid (0.33 / 0.67, median)."""
    lo, hi = train["momentum_24h"].quantile([0.33, 0.67])
    vmed = train["realized_vol_7d"].median()
    return pd.DataFrame({
        "trend_regime": np.where(df["momentum_24h"] > hi, "bull", np.where(df["momentum_24h"] <= lo, "bear", "sideways")),
        "vol_regime": np.where(df["realized_vol_7d"] > vmed, "high", "low"),
    }, index=df.index)


class StubGateRunner:
    """Implements packages.contracts_lane_b.GateRunner on the synthetic data."""

    def __init__(self, df: pd.DataFrame, lgbm: LGBMGate | None = None):
        self.df, self.lgbm = df, lgbm

    def evaluate(self, policy_spec: dict, split: str) -> GateEvaluation:
        if split == "test":
            raise PermissionError("StubGateRunner refuses the sealed test split")
        part = self.df[self.df["split"] == split]
        mult = allocation(policy_spec, part, lgbm=self.lgbm)
        sim, base = simulate(part, mult), simulate(part, pd.Series(1.0, index=part.index))
        key = (sorted((k, str(v)) for k, v in policy_spec.items()), split)
        rng = _rng_for(key)
        m, b = metrics(sim, rng), metrics(base, _rng_for(("always_on", split)))
        ci = _boot_ci([sim["net"].values, base["net"].values], lambda g, a: _compound(g) - _compound(a), _rng_for(key, "delta"))
        aid = "audit_" + hashlib.sha256(repr(key).encode()).hexdigest()[:10]
        return GateEvaluation(policy_id=policy_spec.get("policy_id", "unnamed"), split=split, metrics=m, always_on=b,
                              delta_net_return_vs_always_on=m.net_return - b.net_return, ci_delta=ci,
                              allocation_mix={str(k): float((mult == k).mean()) for k in (0.0, 0.5, 1.0)}, audit_id=aid)


def build(seed: int = 3):
    """Returns (ExperimentResult, StubGateRunner, train_quantiles, market_df, lgbm_gate)."""
    df = make_market(seed=seed)
    train = df[df["split"] == "train"]
    coverage = {f: float(train[f].notna().mean())
                for f in ("momentum_24h", "realized_vol_7d", "volume_zscore", "fear_greed", "news_sentiment")}
    qs = (0.2, 0.33, 0.5, 0.67, 0.8)
    train_quantiles = {f: {q: float(train[f].quantile(q)) for q in qs} for f in coverage}

    labels = regime_labels(df, train)
    always = simulate(df, pd.Series(1.0, index=df.index))
    entries = pd.Series((np.diff(np.concatenate([[0.0], always["q"].values])) > 0), index=df.index)   # on the FULL series
    rows, costs, baselines, windows = [], [], [], []
    rule = rule_gate_spec(train_quantiles)
    for split in ("train", "validation", "test"):
        m = df["split"] == split
        part = df[m]
        windows.append(Window(split=split, start=part["decision_time"].iloc[0].to_pydatetime(), end=part["decision_time"].iloc[-1].to_pydatetime()))
        for feat in ("trend_regime", "vol_regime"):
            for bkt in sorted(labels.loc[m, feat].unique()):
                mm = m & (labels[feat] == bkt)
                s = always[mm]
                lo, hi = _boot_ci([s["net"].values], np.mean, _rng_for("regime", split, feat, bkt))
                rows.append(RegimeRow(split=split, regime_feature=feat, bucket=bkt, n_decisions=int(mm.sum()),
                                      n_trades=int(entries[mm].sum()), mean_net_return=float(s["net"].mean()), ci_low=lo, ci_high=hi,
                                      total_cost=float(s["cost"].sum()),
                                      hit_rate=float((s.loc[s["q"] > 0, "net"] > 0).mean()) if (s["q"] > 0).any() else None))
        s = always[m]
        total_cost = float(s["cost"].sum())
        # always-on has no gate toggling, so all costs are the strategy's own fees + slippage; 'switching' is
        # reserved for costs CAUSED by a gate and is 0 here. gross - fees - slippage - switching = net (summed).
        costs.append(CostBreakdown(split=split, gross_return=float(s["gross"].sum()), fees=total_cost * FEE_SHARE,
                                   slippage=total_cost * (1 - FEE_SHARE), switching=0.0, net_return=float(s["net"].sum()),
                                   turnover=float(np.abs(np.diff(np.concatenate([[0], s["q"].values]))).sum())))
        for name, spec in (("always_on", {"family": "always_on"}), ("cash", {"family": "cash"}), ("simple_rule", rule)):
            baselines.append(BaselineRow(split=split, policy=name,
                                         metrics=metrics(simulate(part, allocation(spec, part)), _rng_for("baseline", name, split))))

    lgbm = LGBMGate()
    tr_m = (df["split"] == "train") & (df["target_position"] > 0)
    lgbm.fit(df[tr_m], df.loc[tr_m, "ret_next"], split="train")

    snap = hashlib.sha256(pd.util.hash_pandas_object(df[["decision_time", "close"]]).values.tobytes()).hexdigest()[:16]
    exp = ExperimentResult(
        experiment_id=f"exp_fixture_{snap[:8]}", strategy_id="btc-momentum-24h-demo", strategy_version="fixture-v1",
        dataset_snapshot_id=f"synthetic:{snap}", dataset_hashes={"market": snap}, windows=windows, per_regime=rows,
        costs=costs, baselines=baselines, coverage=coverage, audit_ids=[f"fixture_{snap[:8]}"],
    )
    return exp, StubGateRunner(df, lgbm=lgbm), train_quantiles, df, lgbm
