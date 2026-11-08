"""Lane B output models (AGENTS.md, Lane B step 1).

Every claim an agent makes must point at evidence IDs that exist in the EvidenceStore,
i.e. at real tool output. The validators that enforce that live in agents.py and
investigate.py; these models only define the shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .allowlist import ALLOCATIONS, GATE_FAMILIES, GATE_FEATURES


class Evidence(BaseModel):
    evidence_id: str
    tool: str                      # which allowlisted tool produced it
    args: dict
    payload: dict                  # the tool's raw output, stored verbatim
    created_at: datetime


class Hypothesis(BaseModel):
    hypothesis_id: str = Field(description="short id like H1, H2")
    statement: str = Field(max_length=400, description="falsifiable statement about WHEN the strategy works or fails; "
                                                       "any number must be copied from cited evidence")
    direction: Literal["works_better", "works_worse"]
    conditions: list[str] = Field(description="regime buckets from regime_performance rows, e.g. ['vol_regime=high']")
    evidence_ids: list[str] = Field(min_length=1, description="ids of tool outputs supporting this; must exist")
    confidence: Literal["low", "medium", "high"]
    caveats: list[str] = Field(default_factory=list)
    suggested_test: str = Field(max_length=300)


class DiagnosticReport(BaseModel):
    summary: str = Field(max_length=800)
    hypotheses: list[Hypothesis] = Field(min_length=1, max_length=6)
    rejected_explanations: list[str] = Field(default_factory=list, description="explanations considered and why rejected")
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique(self):
        ids = [h.hypothesis_id for h in self.hypotheses]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate hypothesis_id in {ids}")
        return self


class ContextFinding(BaseModel):
    finding_id: str
    statement: str = Field(description="what co-occurred in time; never a causal claim")
    episode_ids: list[str] = Field(default_factory=list, description="worst_week_n / best_week_n from sentiment_episodes")
    evidence_ids: list[str] = Field(min_length=1)
    tally: Literal["worst_weeks_after_greed_to_fear_flip", "best_weeks_after_fear_to_greed_flip",
                   "worst_weeks_after_fear_to_greed_flip", "best_weeks_after_greed_to_fear_flip"] | None = Field(
        default=None, description="the sentiment_episodes tally this finding reports, if any")
    strength: Literal["none", "weak", "moderate"] = Field(
        description="'moderate' only for a PRIMARY tally whose binomial_p_value is below 0.05; usually 'weak' or 'none'")
    caveats: list[str] = Field(default_factory=list)


class ContextReport(BaseModel):
    """Agent 4 (context): market sentiment around the strategy's best and worst TRAIN weeks. Co-occurrence only."""
    summary: str = Field(max_length=800)
    findings: list[ContextFinding] = Field(default_factory=list, max_length=6)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique(self):
        ids = [f.finding_id for f in self.findings]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate finding_id in {ids}")
        return self


class ThresholdCondition(BaseModel):
    feature: str
    op: Literal["<=", ">"]
    threshold: float


class GateProposal(BaseModel):
    """An allowlisted supervisory policy. Never a change to the strategy itself."""
    proposal_id: str
    family: Literal["threshold_gate"] = "threshold_gate"
    based_on: list[str] = Field(min_length=1, description="hypothesis ids")
    conditions: list[ThresholdCondition] = Field(min_length=1, max_length=2)
    allocation_when_true: float
    allocation_when_false: float
    rationale: str = Field(max_length=400)
    evidence_ids: list[str] = Field(min_length=1)
    falsification_test: str = Field(max_length=300, description="what result on validation would reject this gate")

    def to_policy_spec(self) -> dict:
        return {
            "policy_id": f"agent::{self.proposal_id}",
            "family": self.family,
            "conditions": [c.model_dump() for c in self.conditions],
            "allocation_when_true": self.allocation_when_true,
            "allocation_when_false": self.allocation_when_false,
            "thresholds_selected_on": "train",
        }


class ProposalSet(BaseModel):
    proposals: list[GateProposal] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def _unique(self):
        ids = [p.proposal_id for p in self.proposals]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate proposal_id in {ids}")
        return self


class Critique(BaseModel):
    proposal_id: str
    verdict: Literal["approve_for_frozen_test", "reject", "needs_change"]
    leakage_concerns: list[str] = Field(default_factory=list)
    overfit_risks: list[str] = Field(default_factory=list)
    fragile_samples: list[str] = Field(default_factory=list, description="BLOCKING sample-size/fragility issues only; "
                                                                         "the arbiter treats any entry as disqualifying")
    counterexamples: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list, description="non-blocking remarks")
    evidence_ids: list[str] = Field(min_length=1, description="must include the gate's own evaluation evidence")


class CritiqueSet(BaseModel):
    critiques: list[Critique] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self):
        ids = [c.proposal_id for c in self.critiques]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate critique for {ids}")
        return self


TrialSource = Literal["agent", "arbiter", "rule_baseline", "meta_model"]


class TrialRecord(BaseModel):
    """Every attempted policy is logged, not only the winner (multiple-comparison honesty)."""
    policy_id: str
    spec_hash: str | None = None
    source: TrialSource
    split: Literal["train", "validation", "test"]
    delta_net_return_vs_always_on: float | None
    ci_delta: tuple[float, float] | None
    net_return: float | None = None              # the policy's own compounded net return (= delta vs cash)
    allocation_mix: dict[str, float] = Field(default_factory=dict)
    evidence_id: str | None
    status: Literal["evaluated", "refused", "error"]   # late results after a stage timeout: "error" with note "abandoned: ..."
    note: str = ""
    fold: int | None = None                      # walk-forward train fold (arbiter only); None for every other trial


class PolicyCandidate(BaseModel):
    policy_id: str
    spec_hash: str | None = None
    source: Literal["agent", "rule_baseline", "meta_model"]
    role: Literal["agent_champion", "agent_not_selected", "competitor"]
    policy_spec: dict
    status: Literal["accepted_for_frozen_test", "rejected", "competitor"]
    validation_delta_vs_always_on: float | None = None
    validation_ci: tuple[float, float] | None = None
    validation_delta_vs_simple_rule: float | None = None
    validation_delta_vs_cash: float | None = None
    allocation_mix: dict[str, float] = Field(default_factory=dict, description="share of IN-POSITION decisions at each multiplier")
    reasons: list[str] = Field(description="arbiter reasons; text quoted from the critic is prefixed 'critic:'")
    evidence_ids: list[str]


class InvestigationReport(BaseModel):
    experiment_id: str
    strategy_id: str
    generated_at: datetime
    agent_mode: Literal["llm", "llm_with_fallback", "deterministic_fallback"]   # Lane C / API contract
    model_id: str | None
    agent_failures: list[str] = Field(default_factory=list)
    verdict: Literal["candidate_for_frozen_test", "INCONCLUSIVE"]   # did an agent gate earn one sealed look?
    # (the strategy-level KEEP / ACTIVATE / KILL decision belongs to Lane A's arbiter: docs/INTEGRATION_DECISIONS.md)
    verdict_basis: list[str] = Field(default_factory=list)
    champion_policy_id: str | None
    validation_always_on: dict = Field(default_factory=dict)   # net return + CI of the unchanged strategy on validation
    validation_cash_net_return: float = 0.0
    diagnostic: DiagnosticReport
    proposals: list[GateProposal]
    critiques: list[Critique]
    trial_log: list[TrialRecord]
    candidates: list[PolicyCandidate]
    test_requests: list[str]
    limitations: list[str]
    evidence: list[Evidence]
    n_distinct_agent_policies: int
    n_policies_tried: int
    holdout_accessed: bool = False
    strategy_health: dict | None = None   # bad luck vs broken (spec section 8); code-computed, see health.py
    context: ContextReport | None = None  # agent 4: sentiment around the best/worst train weeks (context.py)
    # optional plain-language view built by code from the fields above (presentation.py); adds no numbers or decisions
    presentation: dict | None = None


__all__ = [
    "ALLOCATIONS", "GATE_FAMILIES", "GATE_FEATURES",
    "Evidence", "Hypothesis", "DiagnosticReport", "ContextFinding", "ContextReport", "ThresholdCondition", "GateProposal", "ProposalSet",
    "Critique", "CritiqueSet", "TrialRecord", "PolicyCandidate", "InvestigationReport",
]
