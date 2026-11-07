"""PydanticAI agents (AGENTS.md Lane B steps 3-5): diagnostic analyst, gate proposer, critic.

Agents can only call the allowlisted tools in tools.py through a ToolContext (deps).
Output validators reject, and make the model retry on, any output that:
  - cites an evidence id that no tool produced;
  - proposes a gate outside the allowlist / off the training-quantile grid;
  - refers to a hypothesis that doesn't exist.
Agents never see the test split, never change strategy code, never produce an order.

Model is configured with KOK_AGENT_MODEL (any PydanticAI model string, e.g.
"google-gla:gemini-2.5-flash" with GEMINI_API_KEY set). Unset -> callers use the
deterministic fallback in fallback.py.
"""

from __future__ import annotations

import json
import os

from pydantic_ai import Agent, ModelRetry, RunContext

from .allowlist import ALLOCATIONS, GATE_FEATURES, check_gate
from .models import CritiqueSet, DiagnosticReport, ProposalSet
from .tools import HoldoutAccessError, ToolContext

MODEL_ENV = "KOK_AGENT_MODEL"


def configured_model() -> str | None:
    return os.environ.get(MODEL_ENV) or None


# ------------------------------------------------------------------ tool wrappers (what the LLM sees)

def regime_performance(ctx: RunContext[ToolContext], split: str = "train", regime_feature: str | None = None) -> dict:
    """Conditional performance of the UNCHANGED strategy by regime bucket. split: 'train' or 'validation'.
    regime_feature: optional, e.g. 'trend_regime' or 'vol_regime'. Returns rows and an evidence_id to cite."""
    try:
        return ctx.deps.regime_performance(split, regime_feature)
    except HoldoutAccessError as exc:
        ctx.deps.holdout_accessed = True
        return {"error": str(exc)}


def cost_attribution(ctx: RunContext[ToolContext], split: str = "train") -> dict:
    """Gross vs net, fees, slippage, switching costs and baselines (always_on, cash, simple_rule) for a split."""
    try:
        return ctx.deps.cost_attribution(split)
    except HoldoutAccessError as exc:
        ctx.deps.holdout_accessed = True
        return {"error": str(exc)}


def news_context(ctx: RunContext[ToolContext], start: str, end: str, decision_cutoff: str | None = None) -> dict:
    """Point-in-time news first seen between start and end (ISO datetimes, UTC), not after decision_cutoff.
    Contextual evidence only, never causal proof."""
    try:
        return ctx.deps.news_context(start, end, decision_cutoff)
    except HoldoutAccessError as exc:
        ctx.deps.holdout_accessed = True
        return {"error": str(exc)}


def feature_grid(ctx: RunContext[ToolContext]) -> dict:
    """Allowlisted gate features, their coverage, and the ONLY thresholds you may use (training quantiles)."""
    return ctx.deps.feature_grid()


def test_gate_train(ctx: RunContext[ToolContext], conditions: list[dict], allocation_when_true: float,
                    allocation_when_false: float, policy_id: str) -> dict:
    """Evaluate a threshold gate on the TRAIN split only. conditions: list of
    {"feature": str, "op": "<=" or ">", "threshold": float}; thresholds must come from feature_grid.
    Allocations must be 0.0, 0.5 or 1.0. Every call is logged and counts against a fixed budget."""
    spec = {"policy_id": f"agent::{policy_id}", "family": "threshold_gate", "conditions": conditions,
            "allocation_when_true": allocation_when_true, "allocation_when_false": allocation_when_false,
            "thresholds_selected_on": "train"}
    return ctx.deps.test_gate_train(spec, split="train", source="agent")


def lookup_evidence(ctx: RunContext[ToolContext], evidence_id: str) -> dict:
    """Return a stored tool output by its evidence_id."""
    if evidence_id not in ctx.deps.store:
        return {"error": f"unknown evidence id {evidence_id}"}
    return ctx.deps.store.get(evidence_id).model_dump(mode="json")


def trial_log(ctx: RunContext[ToolContext]) -> list[dict]:
    """Every policy attempted so far (including refused ones), with train/validation results."""
    return [t.model_dump() for t in ctx.deps.trials]


# ------------------------------------------------------------------ validators

def _require_evidence(ctx: RunContext[ToolContext], ids: list[str]) -> None:
    missing = ctx.deps.store.missing(ids)
    if missing:
        raise ModelRetry(f"These evidence ids do not exist: {missing}. Cite only evidence_id values returned by tools.")


# ------------------------------------------------------------------ agents

DIAGNOSTIC_INSTRUCTIONS = """You are a quantitative research analyst supervising an EXISTING trading strategy that must not be changed.
Find WHEN it works and when it fails. Use the tools: regime_performance and cost_attribution on 'train' (and 'validation' to check
stability), news_context only as context. Rules: every hypothesis must cite evidence_id values returned by tools; never invent
numbers; treat buckets with fewer than 20 trades or confidence intervals spanning zero as weak; say what would falsify each hypothesis;
news co-occurrence is not causation. The test period is sealed; do not ask for it."""

PROPOSER_INSTRUCTIONS = f"""You propose SUPERVISORY gates for an unchanged strategy: when to run it at full, half or zero size.
You may only use the threshold_gate family with 1-2 conditions on these features: {list(GATE_FEATURES)}; allocations in {list(ALLOCATIONS)};
thresholds MUST be values returned by feature_grid. You may evaluate candidates with test_gate_train (TRAIN only, limited budget,
every attempt is logged and disclosed). Base each proposal on the given hypotheses, cite evidence ids, and state a falsification test
for the validation period. Prefer fewer, simpler gates."""

CRITIC_INSTRUCTIONS = """You are an independent critic. For each proposed gate, look for: look-ahead or leakage, overfitting (many
trials, thresholds chosen after seeing results, effects only in-sample), fragile sample sizes, a gate that is almost always on or off,
and counterexamples in the validation results. Use trial_log and lookup_evidence; cite evidence ids. You cannot change thresholds.
Verdict 'approve_for_frozen_test' only if the evidence on validation supports it."""


def _diagnostic_agent(model) -> Agent:
    agent = Agent(model, output_type=DiagnosticReport, deps_type=ToolContext, instructions=DIAGNOSTIC_INSTRUCTIONS,
                  tools=[regime_performance, cost_attribution, news_context], retries=3, defer_model_check=True)

    @agent.output_validator
    def _v(ctx: RunContext[ToolContext], out: DiagnosticReport) -> DiagnosticReport:
        _require_evidence(ctx, [e for h in out.hypotheses for e in h.evidence_ids])
        return out

    return agent


def _proposer_agent(model, hypothesis_ids: set[str]) -> Agent:
    agent = Agent(model, output_type=ProposalSet, deps_type=ToolContext, instructions=PROPOSER_INSTRUCTIONS,
                  tools=[feature_grid, regime_performance, test_gate_train], retries=3, defer_model_check=True)

    @agent.output_validator
    def _v(ctx: RunContext[ToolContext], out: ProposalSet) -> ProposalSet:
        for p in out.proposals:
            _require_evidence(ctx, p.evidence_ids)
            unknown = set(p.based_on) - hypothesis_ids
            if unknown:
                raise ModelRetry(f"{p.proposal_id}: based_on refers to unknown hypotheses {sorted(unknown)}; valid: {sorted(hypothesis_ids)}")
            problems = check_gate([c.model_dump() for c in p.conditions], p.allocation_when_true, p.allocation_when_false,
                                  ctx.deps.experiment.coverage, ctx.deps.train_quantiles)
            if problems:
                raise ModelRetry(f"{p.proposal_id} violates the allowlist: {problems}. Call feature_grid and use its thresholds.")
        return out

    return agent


def _critic_agent(model) -> Agent:
    agent = Agent(model, output_type=CritiqueSet, deps_type=ToolContext, instructions=CRITIC_INSTRUCTIONS,
                  tools=[trial_log, lookup_evidence], retries=3, defer_model_check=True)

    @agent.output_validator
    def _v(ctx: RunContext[ToolContext], out: CritiqueSet) -> CritiqueSet:
        _require_evidence(ctx, [e for c in out.critiques for e in c.evidence_ids])
        return out

    return agent


def run_diagnostic(ctx: ToolContext, model) -> DiagnosticReport:
    prompt = f"Strategy {ctx.experiment.strategy_id} (version {ctx.experiment.strategy_version}). Diagnose where it works and fails."
    return _diagnostic_agent(model).run_sync(prompt, deps=ctx).output


def run_proposer(ctx: ToolContext, model, diagnostic: DiagnosticReport) -> ProposalSet:
    ids = {h.hypothesis_id for h in diagnostic.hypotheses}
    prompt = "Hypotheses:\n" + json.dumps([h.model_dump() for h in diagnostic.hypotheses], indent=1)
    return _proposer_agent(model, ids).run_sync(prompt, deps=ctx).output


def run_critic(ctx: ToolContext, model, proposals: ProposalSet) -> CritiqueSet:
    prompt = "Proposals to critique:\n" + json.dumps([p.model_dump() for p in proposals.proposals], indent=1)
    return _critic_agent(model).run_sync(prompt, deps=ctx).output
