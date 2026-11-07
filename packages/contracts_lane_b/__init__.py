"""Interfaces Lane B CONSUMES from Lane A (quant/data).

These mirror what AGENTS.md promises: `run_experiment(strategy_id, dataset_snapshot_id,
policy_spec) -> ExperimentResult` with timeseries, per-regime returns, baselines,
uncertainty and audit IDs. When Lane A freezes its schemas in packages/contracts,
replace these with imports from there; field names were chosen to match the spec.

Lane B never computes financial metrics itself. It reads them from these objects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field

Split = Literal["train", "validation", "test"]
DEVELOPMENT_SPLITS: tuple[Split, ...] = ("train", "validation")   # Lane B may only ever read these


class Window(BaseModel):
    split: Split
    start: datetime
    end: datetime


class RegimeRow(BaseModel):
    """Conditional performance of the unchanged strategy in one regime bucket."""
    split: Split
    regime_feature: str            # e.g. "trend_regime", "vol_regime"
    bucket: str                    # e.g. "bull", "high"
    n_decisions: int
    n_trades: int
    mean_net_return: float         # per decision interval, after costs
    ci_low: float                  # block-bootstrap 90% CI (Lane A)
    ci_high: float
    total_cost: float              # fees + slippage + switching, as return fraction
    hit_rate: float | None = None


class CostBreakdown(BaseModel):
    """Compounded over the split. gross - fees - slippage - switching = net.

    switching is gate-driven extra turnover only. On the unchanged strategy it is 0;
    fees and slippage hold that strategy's own turnover.
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


class BaselineRow(BaseModel):
    split: Split
    policy: str                    # "always_on" | "cash" | "simple_rule" | ...
    metrics: Metrics


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
    coverage: dict[str, float] = Field(default_factory=dict)      # feature -> fraction of decisions covered
    audit_ids: list[str] = Field(default_factory=list)


class GateEvaluation(BaseModel):
    """Result of evaluating ONE policy spec on ONE development split (Lane A computes it).

    Convention: net_return is COMPOUNDED simple return over the split, after costs;
    delta = metrics.net_return - always_on.net_return; ci_delta is a block-bootstrap 90%
    interval of that same compounded difference (bars resampled jointly)."""
    policy_id: str
    split: Split
    metrics: Metrics
    always_on: Metrics
    delta_net_return_vs_always_on: float
    ci_delta: tuple[float, float] | None = None
    allocation_mix: dict[str, float] = Field(default_factory=dict)   # share of in-position bars at 0 / 0.5 / 1
    n_decisions: int = 0          # every bar in the split
    n_in_position: int = 0        # bars whose frozen target is not flat; denominator of allocation_mix
    audit_id: str


class GateRunner(Protocol):
    """Lane A provides this. Must refuse split='test' unless the policy is frozen by the arbiter."""

    def evaluate(self, policy_spec: dict, split: Split) -> GateEvaluation: ...
