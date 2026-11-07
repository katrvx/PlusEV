"""Shapes Lane A returns. The subset Lane B reads matches contracts_lane_b on branch lane-b."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Split = Literal["train", "validation", "test"]
DEVELOPMENT_SPLITS: tuple[Split, ...] = ("train", "validation")


class Window(BaseModel):
    split: Split
    start: datetime
    end: datetime


class RegimeRow(BaseModel):
    """Conditional performance of the unchanged strategy in one regime bucket."""

    split: Split
    regime_feature: str
    bucket: str
    n_decisions: int
    n_trades: int
    mean_net_return: float
    ci_low: float
    ci_high: float
    total_cost: float
    hit_rate: float | None = None


class CostBreakdown(BaseModel):
    """Compounded returns. gross − fees − slippage − switching = net.

    fees and slippage are the unchanged strategy's own turnover. switching is
    only the extra turnover a gate adds on top of that path, so it is 0 when
    the row is the strategy itself.
    """

    split: Split
    gross_return: float
    fees: float
    slippage: float
    switching: float
    funding: float = 0.0
    net_return: float
    turnover: float


class Metrics(BaseModel):
    net_return: float
    sharpe: float | None = None
    sortino: float | None = None
    max_drawdown: float
    turnover: float
    n_switches: int
    exposure: float
    ci_net_return: tuple[float, float] | None = None
    cvar_05: float | None = None
    avg_holding_bars: float | None = None


class BaselineRow(BaseModel):
    split: Split
    policy: str
    metrics: Metrics


class EquityPoint(BaseModel):
    decision_time: datetime
    split: Split
    equity: float
    net_return: float
    exposure: float


class ComparisonPoint(BaseModel):
    """Equity index of the pre-registered policies. 1.0 is the start, before the first bar's return."""

    decision_time: datetime
    split: Split
    base: float
    rule: float
    lgbm: float
    cash: float
    regime: float = 1.0


class WalkForwardFold(BaseModel):
    """One expanding fold inside the train window.

    It does not see validation or the sealed test. A critic may read these
    folds. The holdout stays sealed.
    """

    fold: int
    n_fit: int
    n_score: int
    score_start: datetime
    score_end: datetime
    delta_net_return_vs_always_on: float | None = None
    note: str


class FeeCheck(BaseModel):
    """Always-on validation return at a pre-registered cost multiple. Not used to pick a policy."""

    split: Literal["validation"] = "validation"
    scale: float
    fee_bps: float
    slippage_bps: float
    net_return: float


class ExperimentResult(BaseModel):
    experiment_id: str
    strategy_id: str
    strategy_version: str
    dataset_snapshot_id: str
    dataset_hashes: dict[str, str] = Field(default_factory=dict)
    policy_id: str = "always_on"
    windows: list[Window]
    per_regime: list[RegimeRow]
    costs: list[CostBreakdown]
    baselines: list[BaselineRow]
    coverage: dict[str, float] = Field(default_factory=dict)
    missingness: dict[str, dict[str, float]] = Field(default_factory=dict)
    audit_ids: list[str] = Field(default_factory=list)
    equity: list[EquityPoint] = Field(default_factory=list)
    comparison_equity: list[ComparisonPoint] = Field(default_factory=list)
    walk_forward: list[WalkForwardFold] = Field(default_factory=list)
    fee_checks: list[FeeCheck] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    decision: Decision | None = None
    paper_plan: PaperPlan | None = None


class GateEvaluation(BaseModel):
    """One policy, one split. Lane A computes every number.

    allocation_mix is the share of in-position bars at 0, 0.5, and 1.
    A flat target is not a decision the gate can change, so those bars are
    left out of the mix. n_decisions counts every bar in the split.
    n_in_position is the mix denominator.
    """

    policy_id: str
    split: Split
    metrics: Metrics
    always_on: Metrics
    delta_net_return_vs_always_on: float
    ci_delta: tuple[float, float] | None = None
    allocation_mix: dict[str, float] = Field(default_factory=dict)
    n_decisions: int = 0
    n_in_position: int = 0
    audit_id: str


Verdict = Literal[
    "KEEP",
    "MODIFY",
    "COMBINE",
    "RESTRICT",
    "MONITOR",
    "KILL",
    "INCONCLUSIVE",
]


class Decision(BaseModel):
    """Deterministic arbiter output. An LLM does not set this."""

    verdict: Verdict
    policy_id: str
    reasons: list[str]
    risk_override: bool = False
    evidence: dict[str, float] = Field(default_factory=dict)


class PaperPlan(BaseModel):
    """A frozen 14-day shadow plan. Recording it is not a claim that it has run."""

    plan_id: str
    status: Literal["recorded_not_started"] = "recorded_not_started"
    completed: bool = False
    approved: bool = False
    horizon_days: int = 14
    strategy_id: str
    strategy_version: str
    champion_policy_id: str
    challenger_policy_id: str
    frozen_at_experiment: str
    cost_assumptions: str
    predictive_range_low: float | None = None
    predictive_range_high: float | None = None
    predictive_horizon_bars: int | None = None
    notes: list[str]
