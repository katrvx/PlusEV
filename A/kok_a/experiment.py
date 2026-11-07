"""Chronological experiment: frozen strategy, regimes, baselines, sealed holdout.

`run_experiment` scores the pre-registered comparison (always-on, cash, simple
rule, LightGBM) on every split, including the last 20% once. `GateRunner.evaluate`
is what agents call, and it refuses that test split.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from kok_a.arbiter import build_paper_plan, decide
from kok_a.contracts import (
    BaselineRow,
    ComparisonPoint,
    CostBreakdown,
    EquityPoint,
    ExperimentResult,
    FeeCheck,
    GateEvaluation,
    Metrics,
    RegimeRow,
    WalkForwardFold,
    Window,
)
from kok_a.features import FEATURE_COLUMNS, build_frame, coverage_table
from kok_a.gates import allocation, rule_gate_spec
from kok_a.lgbm_gate import LGBMGate
from kok_a.market import hash_ohlcv
from kok_a.simulate import ANNUALIZATION, FEE_BPS, SLIPPAGE_BPS, block_ci, simulate
from kok_a.snapshot import SNAPSHOT_READY, SNAPSHOT_SYNTHETIC, load_inputs
from kok_a.strategies import positions

QUANTILES = (0.2, 0.33, 0.5, 0.67, 0.8)
SPLITS = ("train", "validation", "test")
EMBARGO_BARS = 2
WALK_FORWARD_FOLDS = 4
PAPER_HORIZON_BARS = 14 * 24
REQUIRED_FEATURES = (
    "momentum_24h",
    "momentum_7d",
    "realized_vol_7d",
    "atr_14",
    "price_drawdown",
    "volume_zscore",
    "target_position",
    "ret_next",
)


@dataclass
class Bundle:
    result: ExperimentResult
    runner: "GateRunner"
    frame: pd.DataFrame
    lgbm: LGBMGate
    quantiles: dict[str, dict[float, float]]
    thresholds: dict


class GateRunner:
    """Scores a policy. `evaluate` is development-only; `evaluate_frozen` may read the test split once per policy id."""

    def __init__(
        self,
        frame: pd.DataFrame,
        lgbm: LGBMGate,
        seed: int,
        n_boot: int,
        snapshot_id: str,
        thresholds: dict,
        fee_bps: float = FEE_BPS,
        slippage_bps: float = SLIPPAGE_BPS,
    ):
        self.frame = frame
        self.lgbm = lgbm
        self.seed = seed
        self.n_boot = n_boot
        self.snapshot_id = snapshot_id
        self.thresholds = thresholds
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.holdout_log: list[str] = []
        self._frozen: dict[str, tuple[str, GateEvaluation]] = {}

    def evaluate(self, policy_spec: dict, split: str) -> GateEvaluation:
        if split == "test":
            raise PermissionError("sealed test split; GateRunner.evaluate refuses it")
        if split not in ("train", "validation"):
            raise ValueError(f"unknown split {split}")
        return self._score(policy_spec, split, reveal=(split,))

    def evaluate_frozen(self, policy_spec: dict) -> GateEvaluation:
        """One look at the test split for this exact policy. A changed body under the same id is refused."""

        policy_id = str(policy_spec.get("policy_id", "unnamed"))
        body = json.dumps(policy_spec, sort_keys=True, default=str)
        cached = self._frozen.get(policy_id)
        if cached is not None:
            if cached[0] != body:
                raise PermissionError(
                    f"{policy_id} was already tested on the holdout; a changed policy needs a new untouched period"
                )
            return cached[1]
        evaluation = self._score(policy_spec, "test", reveal=("test",))
        self._frozen[policy_id] = (body, evaluation)
        self.holdout_log.append(policy_id)
        return evaluation

    def _score(self, policy_spec: dict, split: str, reveal: tuple[str, ...]) -> GateEvaluation:
        multiplier = allocation(policy_spec, self.frame, lgbm=self.lgbm)
        visible = self.frame["split"].isin(reveal).to_numpy()
        scored = simulate(self.frame, multiplier, visible=visible, fee_bps=self.fee_bps, slippage_bps=self.slippage_bps)
        baseline = simulate(
            self.frame,
            pd.Series(1.0, index=self.frame.index),
            visible=visible,
            fee_bps=self.fee_bps,
            slippage_bps=self.slippage_bps,
        )
        mask = self.frame["split"] == split
        part = scored.loc[mask]
        base = baseline.loc[mask]
        policy_id = str(policy_spec.get("policy_id", "unnamed"))
        policy_metrics = _metrics(part, _rng(self.seed, policy_id, split, "net"), self.n_boot)
        always_metrics = _metrics(base, _rng(self.seed, "always_on", split, "net"), self.n_boot)
        policy_net = part["net"].to_numpy(dtype=float)
        base_net = base["net"].to_numpy(dtype=float)
        return GateEvaluation(
            policy_id=policy_id,
            split=split,  # type: ignore[arg-type]
            metrics=policy_metrics,
            always_on=always_metrics,
            delta_net_return_vs_always_on=policy_metrics.net_return - always_metrics.net_return,
            ci_delta=_paired_compound_ci(policy_net, base_net, _rng(self.seed, policy_id, split, "delta"), self.n_boot),
            allocation_mix=_allocation_mix(multiplier.loc[mask]),
            audit_id=_audit(policy_spec, split, self.snapshot_id),
        )


def run_experiment(
    strategy_id: str,
    dataset_snapshot_id: str,
    policy_spec: dict | None = None,
    *,
    n: int = 1600,
    seed: int = 7,
    n_boot: int = 200,
    n_estimators: int = 120,
) -> ExperimentResult:
    return assemble(
        strategy_id,
        dataset_snapshot_id,
        policy_spec,
        n=n,
        seed=seed,
        n_boot=n_boot,
        n_estimators=n_estimators,
    ).result


def load_for_lane_b(experiment_id: str = ""):
    """(ExperimentResult, GateRunner, train quantiles, news store, LGBMGate).

    This is the loader `investigate` calls. The result is the development view:
    train and validation only. Sealed-test metrics, the verdict, and the paper
    plan are left off, because those are computed from the holdout.
    `experiment_id` selects the run. News is None: this lane has no first-seen archive.
    """

    strategy_id = "btc-trend-24-72-demo"
    snapshot_id = SNAPSHOT_READY
    kwargs: dict = {}
    if experiment_id in {"", SNAPSHOT_READY, strategy_id}:
        pass
    elif experiment_id == "btc-meanrev-48-demo":
        strategy_id = experiment_id
    elif experiment_id in {SNAPSHOT_SYNTHETIC, "synthetic"}:
        snapshot_id = SNAPSHOT_SYNTHETIC
        kwargs = {"n": 1100, "seed": 7, "n_boot": 30, "n_estimators": 40}
    else:
        known = ", ".join([SNAPSHOT_READY, "btc-trend-24-72-demo", "btc-meanrev-48-demo", SNAPSHOT_SYNTHETIC])
        raise KeyError(f"unknown experiment_id {experiment_id!r}; known: {known}")
    bundle = assemble(strategy_id, snapshot_id, **kwargs)
    return agent_view(bundle.result), bundle.runner, bundle.quantiles, None, bundle.lgbm


def agent_view(result: ExperimentResult) -> ExperimentResult:
    """Copy a result with sealed-test performance removed.

    The test window's dates stay, so a news request that crosses into the
    holdout can still be refused. The runner itself is unchanged and still
    refuses `evaluate(..., "test")`.
    """

    note = (
        "Sealed-test metrics, the verdict, and the paper plan are omitted from this view. "
        "GateRunner.evaluate refuses split='test'."
    )
    notes = list(result.notes)
    if note not in notes:
        notes.append(note)
    return result.model_copy(
        update={
            "baselines": [row for row in result.baselines if row.split != "test"],
            "per_regime": [row for row in result.per_regime if row.split != "test"],
            "costs": [row for row in result.costs if row.split != "test"],
            "equity": [point for point in result.equity if point.split != "test"],
            "comparison_equity": [point for point in result.comparison_equity if point.split != "test"],
            "decision": None,
            "paper_plan": None,
            "notes": notes,
        }
    )


def score_frozen(runner: GateRunner, policy_specs: list[dict]) -> list[GateEvaluation]:
    """One sealed-test look per policy. A changed body under the same id is refused."""

    return [runner.evaluate_frozen(spec) for spec in policy_specs]


def assemble(
    strategy_id: str,
    dataset_snapshot_id: str,
    policy_spec: dict | None = None,
    *,
    n: int = 1600,
    seed: int = 7,
    n_boot: int = 200,
    n_estimators: int = 120,
    external_positions: pd.DataFrame | None = None,
    fee_bps: float | None = None,
    slippage_bps: float | None = None,
) -> Bundle:
    fee = FEE_BPS if fee_bps is None else float(fee_bps)
    slip = SLIPPAGE_BPS if slippage_bps is None else float(slippage_bps)
    ohlcv, fear_greed, provenance = load_inputs(dataset_snapshot_id, n=n, seed=seed)
    frame = build_frame(ohlcv, fear_greed=fear_greed)
    version, sample = _analysis_sample(frame, strategy_id, external_positions)
    labels, thresholds = fit_regime_labels(sample)
    sample = sample.copy()
    sample["trend_regime"] = labels["trend_regime"]
    sample["vol_regime"] = labels["vol_regime"]
    model = _fit_lgbm(sample, seed=seed, n_estimators=n_estimators)
    quantiles = _train_quantiles(sample)
    market_hash = hash_ohlcv(ohlcv)
    signal_hash = _hash_signals(sample)
    runner = GateRunner(
        sample,
        model,
        seed=seed,
        n_boot=n_boot,
        snapshot_id=market_hash,
        thresholds=thresholds,
        fee_bps=fee,
        slippage_bps=slip,
    )
    rule = rule_gate_spec(sample[sample["split"] == "train"])
    runner.rule_spec = rule

    named_policies: list[tuple[str, dict]] = [
        ("always_on", {"policy_id": "always_on", "family": "always_on"}),
        ("cash", {"policy_id": "cash", "family": "cash"}),
        ("simple_rule", rule),
        ("lgbm_gate", model.spec()),
    ]
    if policy_spec is not None:
        named_policies.append((str(policy_spec.get("policy_id", "custom")), policy_spec))

    baselines: list[BaselineRow] = []
    scored: dict[tuple[str, str], GateEvaluation] = {}
    for name, spec in named_policies:
        splits = SPLITS if name in ("always_on", "cash", "simple_rule", "lgbm_gate") else ("train", "validation")
        if policy_spec is not None and spec is policy_spec and policy_spec.get("frozen_for_holdout"):
            splits = SPLITS
        for split in splits:
            if split == "test" and name not in ("always_on", "cash", "simple_rule", "lgbm_gate"):
                evaluation = runner.evaluate_frozen(spec)
            else:
                evaluation = runner._score(spec, split, reveal=SPLITS)
            scored[(name, split)] = evaluation
            baselines.append(BaselineRow(split=split, policy=name, metrics=evaluation.metrics))  # type: ignore[arg-type]

    always = simulate(sample, pd.Series(1.0, index=sample.index), fee_bps=fee, slippage_bps=slip)
    train_net = always.loc[sample["split"] == "train", "net"].to_numpy(dtype=float)
    horizon_range = _predictive_range(train_net, _rng(seed, "paper", "range"), n_boot)
    experiment_id = f"exp_{signal_hash[:12]}"
    n_test = int((sample["split"] == "test").sum())
    decision = decide({name: scored[(name, "test")] for name in ("always_on", "cash", "simple_rule", "lgbm_gate")}, n_test)
    plan = build_paper_plan(
        experiment_id,
        strategy_id,
        version,
        decision,
        f"{fee:.0f} bps fee + {slip:.0f} bp slippage on |change in exposure|",
        horizon_range,
    )
    result = ExperimentResult(
        experiment_id=experiment_id,
        strategy_id=strategy_id,
        strategy_version=version,
        dataset_snapshot_id=dataset_snapshot_id,
        dataset_hashes={"market": market_hash, "signals": signal_hash},
        policy_id=str((policy_spec or {}).get("policy_id", "always_on")),
        windows=_windows(sample),
        per_regime=_regime_rows(sample, always, seed, n_boot),
        costs=_costs(sample, always),
        baselines=baselines,
        coverage=coverage_table(sample)["train"],
        missingness=coverage_table(sample),
        audit_ids=[
            f"market_{market_hash}",
            f"signals_{signal_hash}",
            "pre_registered_holdout:always_on,cash,simple_rule,lgbm_gate",
        ],
        equity=_equity(sample, always),
        comparison_equity=_comparison_equity(sample, runner, fee, slip),
        walk_forward=_walk_forward(sample, seed, n_estimators, fee, slip),
        fee_checks=_fee_checks(sample, fee, slip),
        provenance=provenance,
        notes=_notes(thresholds, provenance, decision.verdict, fee, slip, imported=external_positions is not None),
        decision=decision,
        paper_plan=plan,
    )
    return Bundle(result=result, runner=runner, frame=sample, lgbm=model, quantiles=quantiles, thresholds=thresholds)


def fit_regime_labels(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Three lagged-trend buckets, plus a high/low vol bucket. Cutpoints come from train only."""

    train = frame[frame["split"] == "train"]
    lo, hi = (float(v) for v in train["momentum_24h"].quantile([1.0 / 3.0, 2.0 / 3.0]))
    vol_median = float(train["realized_vol_7d"].median())
    momentum = frame["momentum_24h"].to_numpy(dtype=float)
    vol = frame["realized_vol_7d"].to_numpy(dtype=float)
    trend = np.where(momentum > hi, "bull", np.where(momentum < lo, "bear", "sideways"))
    vol_bucket = np.where(vol > vol_median, "high", "low")
    labels = pd.DataFrame({"trend_regime": trend, "vol_regime": vol_bucket}, index=frame.index)
    return labels, {"momentum_terciles": [lo, hi], "vol_median": vol_median}


def summarize(result: ExperimentResult) -> str:
    lines = [
        f"{result.experiment_id}  {result.strategy_id} ({result.strategy_version})",
        f"snapshot {result.dataset_snapshot_id}",
    ]
    for split in SPLITS:
        lines.append(f"[{split}]")
        for row in result.baselines:
            if row.split != split:
                continue
            metrics = row.metrics
            sharpe = "n/a" if metrics.sharpe is None else f"{metrics.sharpe:.2f}"
            lines.append(
                f"  {row.policy:<12} net {metrics.net_return:+.4f}  sharpe {sharpe}  "
                f"maxDD {metrics.max_drawdown:.3f}  switches {metrics.n_switches}  exposure {metrics.exposure:.2f}"
            )
    coverage = ", ".join(f"{name}={share:.0%}" for name, share in result.coverage.items())
    lines.append(f"train coverage: {coverage}")
    if result.decision is not None:
        lines.append(f"verdict: {result.decision.verdict} via {result.decision.policy_id}")
        lines.extend(result.decision.reasons)
    if result.paper_plan is not None:
        lines.append(
            f"paper plan {result.paper_plan.plan_id}: {result.paper_plan.status}, "
            f"completed={result.paper_plan.completed}, approved={result.paper_plan.approved}"
        )
    lines.extend(result.notes)
    return "\n".join(lines)


def _analysis_sample(
    frame: pd.DataFrame,
    strategy_id: str,
    external_positions: pd.DataFrame | None = None,
) -> tuple[str, pd.DataFrame]:
    sample = frame.copy()
    if external_positions is None:
        version, target = positions(strategy_id, frame["close"])
        sample["target_position"] = target.to_numpy()
    else:
        version = "imported-positions"
        sample["target_position"] = _overlay_positions(sample, external_positions)
    sample = sample.dropna(subset=list(REQUIRED_FEATURES))
    sample = sample.reset_index(drop=True)
    if external_positions is not None:
        sample = _longest_hourly_run(sample)
    if len(sample) < 30:
        if external_positions is not None:
            raise RuntimeError(
                f"only {len(sample)} imported decisions overlap the Binance spot BTCUSDT 1h snapshot "
                "(2024-11-01 through 2026-10-31) after feature warm-up. Need at least 30 consecutive hours."
            )
        raise RuntimeError(f"only {len(sample)} usable decisions after warm-up")
    cut_train = int(len(sample) * 0.6)
    cut_test = int(len(sample) * 0.8)
    split = np.full(len(sample), "validation", dtype=object)
    split[:cut_train] = "train"
    split[cut_test:] = "test"
    sample["split"] = split
    return version, sample


def _embargoed(frame: pd.DataFrame, split: str) -> pd.Series:
    """True except the last EMBARGO_BARS of this split. Their labels reach into the next split."""

    times = frame.loc[frame["split"] == split, "decision_time"]
    if len(times) <= EMBARGO_BARS:
        banned = set(times)
    else:
        banned = set(times.iloc[-EMBARGO_BARS:])
    return ~frame["decision_time"].isin(list(banned))


def _in_market(frame: pd.DataFrame, split: str) -> pd.DataFrame:
    return frame[(frame["split"] == split) & (frame["target_position"] > 0) & _embargoed(frame, split)]


def _fit_lgbm(frame: pd.DataFrame, seed: int, n_estimators: int) -> LGBMGate:
    train = _in_market(frame, "train")
    valid = _in_market(frame, "validation")
    if len(train) < 40 or len(valid) < 10:
        raise RuntimeError("not enough in-market train/validation rows to fit the LightGBM gate")
    if train["ret_next"].gt(0).nunique() < 2:
        raise RuntimeError("train opportunity returns are one-sided; refusing to fit a classifier")
    model = LGBMGate(seed=seed, n_estimators=n_estimators)
    model.fit(train, train["ret_next"], split="train")
    model.calibrate(valid, valid["ret_next"], split="validation")
    return model


def _train_quantiles(frame: pd.DataFrame) -> dict[str, dict[float, float]]:
    train = frame[frame["split"] == "train"]
    found: dict[str, dict[float, float]] = {}
    for name in FEATURE_COLUMNS:
        series = train[name].dropna()
        found[name] = {q: float(series.quantile(q)) for q in QUANTILES} if len(series) else {}
    return found


def _metrics(sim: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> Metrics:
    net = sim["net"].to_numpy(dtype=float)
    if len(net) == 0 or not np.isfinite(net).all():
        raise RuntimeError("metrics received an empty or non-finite return series")
    equity = np.cumprod(1.0 + net)
    drawdown = 1.0 - equity / np.maximum.accumulate(equity)
    deviation = float(net.std(ddof=0))
    downside = net[net < 0]
    downside_deviation = float(downside.std(ddof=0)) if len(downside) else float("nan")
    lo, hi = _compound_ci(net, rng, n_boot=n_boot)
    exposure = sim["q"].to_numpy(dtype=float)
    sharpe = float(net.mean() / deviation * ANNUALIZATION) if deviation > 0 else None
    sortino = float(net.mean() / downside_deviation * ANNUALIZATION) if downside_deviation and downside_deviation > 0 else None
    return Metrics(
        net_return=float(equity[-1] - 1.0),
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=float(drawdown.max()),
        turnover=float(sim["dq"].sum()),
        n_switches=int((sim["dq"] > 1e-12).sum()),
        exposure=float(exposure.mean()),
        ci_net_return=(lo, hi),
        cvar_05=_cvar(net),
        avg_holding_bars=_holding_bars(exposure),
    )


def _regime_rows(frame: pd.DataFrame, always: pd.DataFrame, seed: int, n_boot: int) -> list[RegimeRow]:
    rows: list[RegimeRow] = []
    for split in SPLITS:
        in_split = frame["split"] == split
        for feature in ("trend_regime", "vol_regime"):
            for bucket in sorted(frame.loc[in_split, feature].unique()):
                mask = in_split & (frame[feature] == bucket)
                part = always.loc[mask]
                lo, hi = block_ci(part["net"].to_numpy(), _rng(seed, feature, split, str(bucket)), n_boot=n_boot)
                exposed = part["q"] > 0
                hit = float((part.loc[exposed, "net"] > 0).mean()) if bool(exposed.any()) else None
                rows.append(
                    RegimeRow(
                        split=split,  # type: ignore[arg-type]
                        regime_feature=feature,
                        bucket=str(bucket),
                        n_decisions=int(mask.sum()),
                        n_trades=int((part["dq_signed"] > 1e-12).sum()),
                        mean_net_return=float(part["net"].mean()),
                        ci_low=lo,
                        ci_high=hi,
                        total_cost=float(part["cost"].sum()),
                        hit_rate=hit,
                    )
                )
    return rows


def _costs(frame: pd.DataFrame, always: pd.DataFrame) -> list[CostBreakdown]:
    rows: list[CostBreakdown] = []
    for split in SPLITS:
        part = always.loc[frame["split"] == split]
        rows.append(
            CostBreakdown(
                split=split,  # type: ignore[arg-type]
                gross_return=float(part["gross"].sum()),
                fees=float(part["fees"].sum()),
                slippage=float(part["slippage"].sum()),
                switching=float(part["cost"].sum()),
                net_return=float(part["net"].sum()),
                turnover=float(part["dq"].sum()),
            )
        )
    return rows


def _windows(frame: pd.DataFrame) -> list[Window]:
    windows: list[Window] = []
    for split in SPLITS:
        part = frame[frame["split"] == split]
        windows.append(Window(split=split, start=_py(part["decision_time"].iloc[0]), end=_py(part["decision_time"].iloc[-1])))  # type: ignore[arg-type]
    return windows


def _equity(frame: pd.DataFrame, always: pd.DataFrame) -> list[EquityPoint]:
    equity = np.cumprod(1.0 + always["net"].to_numpy(dtype=float))
    return [
        EquityPoint(
            decision_time=_py(frame["decision_time"].iloc[i]),
            split=frame["split"].iloc[i],
            equity=float(equity[i]),
            net_return=float(always["net"].iloc[i]),
            exposure=float(always["q"].iloc[i]),
        )
        for i in range(len(frame))
    ]


def _comparison_equity(frame: pd.DataFrame, runner: GateRunner, fee_bps: float, slippage_bps: float) -> list[ComparisonPoint]:
    specs = {
        "always_on": {"policy_id": "always_on", "family": "always_on"},
        "cash": {"policy_id": "cash", "family": "cash"},
        "simple_rule": runner.rule_spec,
        "lgbm_gate": runner.lgbm.spec(),
    }
    curves: dict[str, np.ndarray] = {}
    for name, spec in specs.items():
        multiplier = allocation(spec, frame, lgbm=runner.lgbm)
        simulated = simulate(frame, multiplier, fee_bps=fee_bps, slippage_bps=slippage_bps)
        curves[name] = np.cumprod(1.0 + simulated["net"].to_numpy(dtype=float))
    return [
        ComparisonPoint(
            decision_time=_py(frame["decision_time"].iloc[i]),
            split=frame["split"].iloc[i],
            base=float(curves["always_on"][i]),
            rule=float(curves["simple_rule"][i]),
            lgbm=float(curves["lgbm_gate"][i]),
            cash=float(curves["cash"][i]),
        )
        for i in range(len(frame))
    ]


def _walk_forward(frame: pd.DataFrame, seed: int, n_estimators: int, fee_bps: float, slippage_bps: float) -> list[WalkForwardFold]:
    """Expanding folds inside train. The embargo keeps a fold's labels out of the next block."""

    train = frame[frame["split"] == "train"].reset_index(drop=True)
    block = len(train) // WALK_FORWARD_FOLDS
    if block < 40:
        start = _py(train["decision_time"].iloc[0]) if len(train) else datetime.now()
        end = _py(train["decision_time"].iloc[-1]) if len(train) else start
        return [
            WalkForwardFold(
                fold=0,
                n_fit=0,
                n_score=len(train),
                score_start=start,
                score_end=end,
                note="train is too short for 4 expanding folds",
            )
        ]
    folds: list[WalkForwardFold] = []
    for fold in range(1, WALK_FORWARD_FOLDS):
        fit_end = fold * block - EMBARGO_BARS
        score_start = fold * block
        score_end = (fold + 1) * block if fold < WALK_FORWARD_FOLDS - 1 else len(train)
        fit_rows = train.iloc[: max(fit_end, 0)]
        score_rows = train.iloc[score_start:score_end]
        if score_rows.empty:
            continue
        window_start = _py(score_rows["decision_time"].iloc[0])
        window_end = _py(score_rows["decision_time"].iloc[-1])
        in_market = fit_rows[fit_rows["target_position"] > 0]
        if len(in_market) < 40 or in_market["ret_next"].gt(0).nunique() < 2 or len(score_rows) < 20:
            folds.append(
                WalkForwardFold(
                    fold=fold,
                    n_fit=int(len(in_market)),
                    n_score=int(len(score_rows)),
                    score_start=window_start,
                    score_end=window_end,
                    note="fold skipped: not enough in-market rows after the embargo",
                )
            )
            continue
        model = LGBMGate(seed=seed, n_estimators=n_estimators)
        model.fit(in_market, in_market["ret_next"], split="train")
        multiplier = model.allocation(score_rows)
        gated = simulate(score_rows, multiplier, fee_bps=fee_bps, slippage_bps=slippage_bps)
        base = simulate(score_rows, pd.Series(1.0, index=score_rows.index), fee_bps=fee_bps, slippage_bps=slippage_bps)
        delta = _compound(gated["net"].to_numpy(dtype=float)) - _compound(base["net"].to_numpy(dtype=float))
        folds.append(
            WalkForwardFold(
                fold=fold,
                n_fit=int(len(in_market)),
                n_score=int(len(score_rows)),
                score_start=window_start,
                score_end=window_end,
                delta_net_return_vs_always_on=delta,
                note="expanding train fold with a 2-bar embargo; not used to choose the sealed-test policy",
            )
        )
    return folds


def _fee_checks(frame: pd.DataFrame, fee_bps: float, slippage_bps: float) -> list[FeeCheck]:
    visible = (frame["split"] == "validation").to_numpy()
    ones = pd.Series(1.0, index=frame.index)
    checks: list[FeeCheck] = []
    for scale in (0.5, 1.0, 2.0):
        simulated = simulate(frame, ones, visible=visible, fee_bps=fee_bps * scale, slippage_bps=slippage_bps * scale)
        net = simulated.loc[visible, "net"].to_numpy(dtype=float)
        checks.append(
            FeeCheck(
                scale=scale,
                fee_bps=fee_bps * scale,
                slippage_bps=slippage_bps * scale,
                net_return=_compound(net),
            )
        )
    return checks


def _predictive_range(net: np.ndarray, rng: np.random.Generator, n_boot: int) -> tuple[float, float, int] | None:
    """90% range for a 14-day path drawn from the training return distribution."""

    horizon = min(PAPER_HORIZON_BARS, len(net))
    block = 24
    if horizon < block * 2:
        return None
    draws = np.empty(n_boot)
    for i in range(n_boot):
        draws[i] = _compound(net[_path_indices(len(net), horizon, rng, block)])
    return float(np.quantile(draws, 0.05)), float(np.quantile(draws, 0.95)), horizon


def _path_indices(n: int, horizon: int, rng: np.random.Generator, block: int) -> np.ndarray:
    starts = rng.integers(0, n - block + 1, size=horizon // block + 1)
    return np.concatenate([np.arange(start, start + block) for start in starts])[:horizon]


def _compound(values: np.ndarray) -> float:
    return float(np.prod(1.0 + values) - 1.0)


def _block_indices(n: int, rng: np.random.Generator, block: int = 24) -> np.ndarray:
    starts = rng.integers(0, n - block + 1, size=n // block + 1)
    return np.concatenate([np.arange(start, start + block) for start in starts])[:n]


def _compound_ci(net: np.ndarray, rng: np.random.Generator, n_boot: int, block: int = 24) -> tuple[float, float]:
    """90% interval for the compounded return, resampling the same bars together."""

    if len(net) < block * 2:
        return (float("nan"), float("nan"))
    draws = np.empty(n_boot)
    for i in range(n_boot):
        draws[i] = _compound(net[_block_indices(len(net), rng, block)])
    return float(np.quantile(draws, 0.05)), float(np.quantile(draws, 0.95))


def _paired_compound_ci(policy: np.ndarray, base: np.ndarray, rng: np.random.Generator, n_boot: int, block: int = 24) -> tuple[float, float]:
    """90% interval for the difference of compounded returns. Both series share each draw."""

    n = len(policy)
    if n < block * 2 or len(base) != n:
        return (float("nan"), float("nan"))
    draws = np.empty(n_boot)
    for i in range(n_boot):
        idx = _block_indices(n, rng, block)
        draws[i] = _compound(policy[idx]) - _compound(base[idx])
    return float(np.quantile(draws, 0.05)), float(np.quantile(draws, 0.95))


def _allocation_mix(multiplier: pd.Series) -> dict[str, float]:
    values = multiplier.to_numpy(dtype=float)
    return {str(level): float(np.isclose(values, level).mean()) if len(values) else 0.0 for level in (0.0, 0.5, 1.0)}


def _cvar(net: np.ndarray, alpha: float = 0.05) -> float | None:
    if len(net) < 20:
        return None
    cutoff = float(np.quantile(net, alpha))
    tail = net[net <= cutoff]
    if len(tail) == 0:
        return None
    return float(tail.mean())


def _holding_bars(exposure: np.ndarray) -> float:
    in_market = exposure > 1e-12
    if not in_market.any():
        return 0.0
    lengths: list[int] = []
    run = 0
    for flag in in_market:
        if flag:
            run += 1
            continue
        if run:
            lengths.append(run)
            run = 0
    if run:
        lengths.append(run)
    return float(np.mean(lengths))


def _overlay_positions(frame: pd.DataFrame, external: pd.DataFrame) -> np.ndarray:
    """Place imported targets on this snapshot's decision times. Unmatched bars stay missing."""

    table = external.copy()
    table["decision_time"] = pd.to_datetime(table["decision_time"], utc=True)
    table = table.drop_duplicates("decision_time", keep="last")
    lookup = pd.Series(table["target_position"].to_numpy(dtype=float), index=table["decision_time"])
    times = pd.to_datetime(frame["decision_time"], utc=True)
    return times.map(lookup).to_numpy(dtype=float)


def _longest_hourly_run(sample: pd.DataFrame) -> pd.DataFrame:
    """Keep the longest stretch of consecutive hours. A gap is not a continuous position path."""

    if sample.empty:
        return sample
    times = pd.to_datetime(sample["decision_time"], utc=True)
    gap = times.diff().ne(pd.Timedelta(hours=1))
    run_id = gap.cumsum()
    best = run_id.value_counts().idxmax()
    return sample.loc[run_id == best].reset_index(drop=True)


def _notes(
    thresholds: dict,
    provenance: dict[str, str],
    verdict: str,
    fee_bps: float,
    slippage_bps: float,
    imported: bool,
) -> list[str]:
    lo, hi = thresholds["momentum_terciles"]
    cost_per_unit = (fee_bps + slippage_bps) / 10_000
    origin = (
        "Positions are the imported target_position series, aligned to this snapshot's hourly decision times. "
        "Hours without an imported position are left out, and only the longest contiguous run is scored."
        if imported
        else "Strategies are demo generators run on these prices. They are not an imported live strategy and are not claimed as alpha."
    )
    return [
        "Decision at bar close; fill at the next bar's open; PnL is that open to the following open.",
        f"Prices: {provenance['prices']}. Fear & Greed: {provenance['fear_greed']}. News: {provenance['news']}.",
        origin,
        f"Cost is assumed, not measured: {fee_bps:.0f} bps fee + {slippage_bps:.0f} bp slippage "
        f"({cost_per_unit:.4%} of notional per unit of exposure change). No funding.",
        f"Trend regimes are train terciles of lagged 24h momentum ({lo:.5f}, {hi:.5f}); "
        f"vol regime splits at the train median {thresholds['vol_median']:.5f}.",
        "The simple rule allocates 1 when 24h momentum is positive and 7d vol is at or below "
        "the train median, and 0 otherwise.",
        "The label is the next open-to-open return, so the last 2 bars of train and of validation "
        "are embargoed from the LightGBM fit and calibration. Their labels would otherwise fall inside the next split.",
        "Expanding walk-forward folds stay inside train. They are a stability check, not a way to pick the sealed-test policy.",
        "Fee checks resimulate always-on on validation at half, one, and double the assumed cost. The arbiter does not read them.",
        "Spot venue: funding is zero. News is omitted because this snapshot has no first-seen archive.",
        "The test split is scored inside run_experiment only for the pre-registered "
        "always-on, cash, simple-rule and LightGBM policies. GateRunner.evaluate refuses it.",
        f"Verdict {verdict} comes from the deterministic arbiter in kok_a.arbiter. "
        "An interval that still contains zero is INCONCLUSIVE. The 14-day paper plan is recorded and not started.",
    ]


def _hash_signals(frame: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    digest.update(np.round(frame["target_position"].to_numpy(dtype=float), 6).tobytes())
    digest.update(pd.to_datetime(frame["decision_time"], utc=True).astype("int64").to_numpy().tobytes())
    return digest.hexdigest()[:16]


def _audit(policy_spec: dict, split: str, snapshot_id: str) -> str:
    body = json.dumps({"policy": policy_spec, "split": split, "snapshot": snapshot_id}, sort_keys=True, default=str)
    return "audit_" + hashlib.sha256(body.encode()).hexdigest()[:12]


def _rng(seed: int, *parts: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{seed}|{'|'.join(parts)}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def _py(value: object) -> datetime:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.to_pydatetime()
