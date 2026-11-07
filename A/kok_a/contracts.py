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
    provenance: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    decision: Decision | None = None
    paper_plan: PaperPlan | None = None


class GateEvaluation(BaseModel):
    """One policy, one split. Lane A computes every number."""

    policy_id: str
    split: Split
    metrics: Metrics
    always_on: Metrics
    delta_net_return_vs_always_on: float
    ci_delta: tuple[float, float] | None = None
    allocation_mix: dict[str, float] = Field(default_factory=dict)
    audit_id: str


Verdict = Literal[
    "KEEP",
    "ACTIVATE CONDITIONALLY",
    "REDUCE",
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
    notes: list[str]
