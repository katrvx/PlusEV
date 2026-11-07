"""Lane B output models (AGENTS.md, Lane B step 1).

Every claim an agent makes must point at evidence IDs that exist in the EvidenceStore,
i.e. at real tool output. The validators that enforce that live in agents.py and
investigate.py; these models only define the shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .allowlist import ALLOCATIONS, GATE_FAMILIES, GATE_FEATURES


class Evidence(BaseModel):
    evidence_id: str
    tool: str                      # which allowlisted tool produced it
    args: dict
    payload: dict                  # the tool's raw output, stored verbatim
    created_at: datetime


class Hypothesis(BaseModel):
    hypothesis_id: str = Field(description="short id like H1, H2")
    statement: str = Field(max_length=400, description="falsifiable statement about WHEN the strategy works or fails")
    direction: Literal["works_better", "works_worse"]
    conditions: list[str] = Field(description="regime buckets involved, e.g. ['trend_regime=bull', 'vol_regime=low']")
    evidence_ids: list[str] = Field(min_length=1, description="ids of tool outputs supporting this; must exist")
    confidence: Literal["low", "medium", "high"]
    caveats: list[str] = Field(default_factory=list)
    suggested_test: str = Field(max_length=300)


class DiagnosticReport(BaseModel):
    summary: str = Field(max_length=800)
    hypotheses: list[Hypothesis] = Field(min_length=1, max_length=6)
    rejected_explanations: list[str] = Field(default_factory=list, description="explanations considered and why rejected")
    limitations: list[str] = Field(default_factory=list)


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
    proposals: list[GateProposal] = Field(min_length=1, max_length=4)


class Critique(BaseModel):
    proposal_id: str
    verdict: Literal["approve_for_frozen_test", "reject", "needs_change"]
    leakage_concerns: list[str] = Field(default_factory=list)
    overfit_risks: list[str] = Field(default_factory=list)
    fragile_samples: list[str] = Field(default_factory=list)
    counterexamples: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)


class CritiqueSet(BaseModel):
    critiques: list[Critique] = Field(min_length=1)


class TrialRecord(BaseModel):
    """Every attempted policy is logged, not only the winner (multiple-comparison honesty)."""
    policy_id: str
    source: Literal["agent", "rule_baseline", "meta_model"]
    split: Literal["train", "validation"]
    delta_net_return_vs_always_on: float | None
    ci_delta: tuple[float, float] | None
    evidence_id: str | None
    status: Literal["evaluated", "refused", "error"]
    note: str = ""


class PolicyCandidate(BaseModel):
    policy_id: str
    source: Literal["agent", "rule_baseline", "meta_model"]
    policy_spec: dict
    status: Literal["accepted_for_frozen_test", "rejected"]
    reasons: list[str]
    evidence_ids: list[str]


class InvestigationReport(BaseModel):
    experiment_id: str
    strategy_id: str
    generated_at: datetime
    agent_mode: Literal["llm", "deterministic_fallback"]
    model_id: str | None
    diagnostic: DiagnosticReport
    proposals: list[GateProposal]
    critiques: list[Critique]
    trial_log: list[TrialRecord]
    candidates: list[PolicyCandidate]
    test_requests: list[str]
    limitations: list[str]
    evidence: list[Evidence]
    n_policies_tried: int
    holdout_accessed: bool = False


__all__ = [
    "ALLOCATIONS", "GATE_FAMILIES", "GATE_FEATURES",
    "Evidence", "Hypothesis", "DiagnosticReport", "ThresholdCondition", "GateProposal", "ProposalSet",
    "Critique", "CritiqueSet", "TrialRecord", "PolicyCandidate", "InvestigationReport",
]
