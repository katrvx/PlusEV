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
    fragile_samples: list[str] = Field(default_factory=list)
    counterexamples: list[str] = Field(default_factory=list)
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
    allocation_mix: dict[str, float] = Field(default_factory=dict)
    evidence_id: str | None
    status: Literal["evaluated", "refused", "error"]
    note: str = ""


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
    allocation_mix: dict[str, float] = Field(default_factory=dict)
    reasons: list[str]
    evidence_ids: list[str]


class InvestigationReport(BaseModel):
    experiment_id: str
    strategy_id: str
    generated_at: datetime
    agent_mode: Literal["llm", "deterministic_fallback", "llm_with_fallback"]
    model_id: str | None
    agent_failures: list[str] = Field(default_factory=list)
    verdict: Literal["candidate_for_frozen_test", "INCONCLUSIVE"]
    champion_policy_id: str | None
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


__all__ = [
    "ALLOCATIONS", "GATE_FAMILIES", "GATE_FEATURES",
    "Evidence", "Hypothesis", "DiagnosticReport", "ThresholdCondition", "GateProposal", "ProposalSet",
    "Critique", "CritiqueSet", "TrialRecord", "PolicyCandidate", "InvestigationReport",
]
