"""PydanticAI agents (AGENTS.md Lane B steps 3-5): diagnostic analyst, gate proposer, critic.

Agents can only call the allowlisted tools in tools.py through a ToolContext (deps).
Bad tool arguments come back to the model as a retry, never as a crash.
Output validators (shared with the deterministic fallback via verify_*) reject, and
make the model retry on, any output that:
  - cites an evidence id that no tool produced;
  - states a number that does not appear in the cited evidence;
  - names a regime condition that is not in the cited regime_performance rows;
  - proposes a gate outside the allowlist / off the training-quantile grid, or reuses an id;
  - critiques a proposal that doesn't exist, or without citing that gate's own evaluation.
Agents see TRAIN data only; validation results reach the critic only through the
trial log after the arbiter (code) has run them. Agents never see the test split.

Model is configured with KOK_AGENT_MODEL (any PydanticAI model string, e.g.
"google:gemini-3.8-flash" with GEMINI_API_KEY set). Unset -> deterministic fallback.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.usage import UsageLimits

from .allowlist import ALLOCATIONS, GATE_FEATURES, check_gate
from .models import CritiqueSet, DiagnosticReport, ProposalSet, ThresholdCondition
from .tools import HoldoutAccessError, ToolContext, spec_hash

MODEL_ENV = "KOK_AGENT_MODEL"

# Hard bounds so a slow or looping model can never hang the run (any breach -> fallback, disclosed).
STAGE_TIMEOUT_S = float(os.environ.get("KOK_STAGE_TIMEOUT", "240"))     # whole agent stage
REQUEST_TIMEOUT_S = float(os.environ.get("KOK_REQUEST_TIMEOUT", "90"))  # single model request
MAX_REQUESTS = int(os.environ.get("KOK_MAX_REQUESTS", "15"))            # model round-trips per stage


def _log(msg: str) -> None:
    print(f"[agents] {msg}", file=sys.stderr, flush=True)


def _run(agent: Agent, prompt: str, ctx: ToolContext, stage: str):
    _log(f"{stage}: start (timeout {STAGE_TIMEOUT_S:.0f}s, max {MAX_REQUESTS} model requests)")
    t0 = time.monotonic()
    result = agent.run_sync(prompt, deps=ctx, timeout=STAGE_TIMEOUT_S,
                            usage_limits=UsageLimits(request_limit=MAX_REQUESTS),
                            model_settings={"timeout": REQUEST_TIMEOUT_S, "temperature": 0.2})
    u = result.usage() if callable(getattr(result, "usage", None)) else None
    _log(f"{stage}: done in {time.monotonic() - t0:.0f}s" + (f", {u.requests} requests, {u.total_tokens} tokens" if u else ""))
    return result.output


def configured_model() -> str | None:
    return os.environ.get(MODEL_ENV) or None


def model_name(model) -> str | None:
    if model is None:
        return None
    return model if isinstance(model, str) else getattr(model, "model_name", type(model).__name__)


# ------------------------------------------------------------------ claim verification (shared with fallback)

NUM_RE = re.compile(r"(?<![A-Za-z_\d.])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?(?![A-Za-z_\d])")
TRIVIAL = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 90, 95, 100}


def _evidence_numbers(obj, out: list[float]) -> list[float]:
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _evidence_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _evidence_numbers(v, out)
    return out


def unsupported_numbers(text: str, payloads: list[dict]) -> list[str]:
    """Numbers in text that can't be matched (allowing %, bp and print rounding) to any cited payload."""
    nums = _evidence_numbers(payloads, [])
    bad = []
    for tok in NUM_RE.findall(text):
        pct = tok.endswith("%")
        raw = tok.rstrip("%")
        try:
            d = Decimal(raw)
        except InvalidOperation:
            continue
        val = float(d)
        if not pct and val == int(val) and abs(val) in TRIVIAL:
            continue
        tol = 0.5 * 10 ** d.as_tuple().exponent
        targets = [val / 100] if pct else [val, val / 100, val / 1e4]
        if not any(abs(t - v) <= max(tol / (100 if pct else 1), 0.005 * abs(v)) for t in targets for v in nums):
            bad.append(tok)
    return bad


def verify_diagnostic(ctx: ToolContext, out: DiagnosticReport) -> list[str]:
    problems = []
    for h in out.hypotheses:
        missing = ctx.store.missing(h.evidence_ids)
        if missing:
            problems.append(f"{h.hypothesis_id}: unknown evidence ids {missing}")
            continue
        cited = [ctx.store.get(e).payload for e in h.evidence_ids]
        buckets = {f"{r['regime_feature']}={r['bucket']}" for p in cited for r in p.get("rows", [])}
        bad_conds = [c for c in h.conditions if c not in buckets]
        if bad_conds:
            problems.append(f"{h.hypothesis_id}: conditions {bad_conds} are not regime buckets in the cited regime_performance rows {sorted(buckets)}")
        bad_nums = unsupported_numbers(h.statement, cited)
        if bad_nums:
            problems.append(f"{h.hypothesis_id}: numbers {bad_nums} do not appear in the cited evidence")
    bad_summary = unsupported_numbers(out.summary, [e.payload for e in ctx.store.all()])
    if bad_summary:
        problems.append(f"summary: numbers {bad_summary} do not appear in any tool output")
    return problems


def verify_proposals(ctx: ToolContext, out: ProposalSet, hypothesis_ids: set[str]) -> list[str]:
    problems = []
    for p in out.proposals:
        missing = ctx.store.missing(p.evidence_ids)
        if missing:
            problems.append(f"{p.proposal_id}: unknown evidence ids {missing}")
        unknown = set(p.based_on) - hypothesis_ids
        if unknown:
            problems.append(f"{p.proposal_id}: based_on refers to unknown hypotheses {sorted(unknown)}; valid: {sorted(hypothesis_ids)}")
        issues = check_gate([c.model_dump() for c in p.conditions], p.allocation_when_true, p.allocation_when_false,
                            ctx.experiment.coverage, ctx.train_quantiles)
        if issues:
            problems.append(f"{p.proposal_id} violates the allowlist: {issues}. Call feature_grid and use its thresholds.")
    return problems


def verify_critiques(ctx: ToolContext, out: CritiqueSet, proposals: ProposalSet) -> list[str]:
    problems = []
    by_id = {p.proposal_id: spec_hash(p.to_policy_spec()) for p in proposals.proposals}
    seen = {c.proposal_id for c in out.critiques}
    if seen != set(by_id):
        problems.append(f"critique exactly these proposals: {sorted(by_id)} (got {sorted(seen)})")
    for c in out.critiques:
        missing = ctx.store.missing(c.evidence_ids)
        if missing:
            problems.append(f"{c.proposal_id}: unknown evidence ids {missing}")
            continue
        h = by_id.get(c.proposal_id)
        own = [e for e in c.evidence_ids if ctx.store.get(e).payload.get("spec_hash") == h]
        if h and not own:
            problems.append(f"{c.proposal_id}: cite at least one evaluation of this exact gate (see trial_log evidence_id)")
    return problems


# ------------------------------------------------------------------ tool wrappers (what the LLM sees)

def _retry_on_bad_args(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except HoldoutAccessError:
            raise
        except (ValueError, TypeError, KeyError, ValidationError) as exc:
            raise ModelRetry(f"bad arguments: {type(exc).__name__}: {exc}") from exc
    wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
    wrapper.__annotations__ = fn.__annotations__
    return wrapper


def _train_only(ctx: RunContext[ToolContext], split: str) -> dict | None:
    _log(f"  tool call: split={split!r}")
    if split == "train":
        return None
    if isinstance(split, str) and split.strip().lower() == "test":
        ctx.deps.attempt_holdout("agent_tool_call")
        return {"error": "the test split is sealed"}
    return {"error": "agents may only read the 'train' split; validation is reserved for the arbiter"}


def regime_performance(ctx: RunContext[ToolContext], split: str = "train", regime_feature: str | None = None) -> dict:
    """Conditional performance of the UNCHANGED strategy by regime bucket on the TRAIN split.
    regime_feature: optional, e.g. 'trend_regime' or 'vol_regime'. Returns rows and an evidence_id to cite."""
    blocked = _train_only(ctx, split)
    return blocked or ctx.deps.regime_performance("train", regime_feature)


def cost_attribution(ctx: RunContext[ToolContext], split: str = "train") -> dict:
    """Gross vs net, fees, slippage, switching costs and baselines (always_on, cash, simple_rule) on TRAIN."""
    blocked = _train_only(ctx, split)
    return blocked or ctx.deps.cost_attribution("train")


def news_context(ctx: RunContext[ToolContext], start: str, end: str, decision_cutoff: str | None = None) -> dict:
    """Point-in-time news first seen between start and end (ISO datetimes; naive = UTC), not after decision_cutoff.
    Only the development period is available. Contextual evidence only, never causal proof."""
    try:
        return _retry_on_bad_args(ctx.deps.news_context)(start, end, decision_cutoff)
    except HoldoutAccessError as exc:
        ctx.deps.attempt_holdout("news_context")
        return {"error": str(exc)}


def feature_grid(ctx: RunContext[ToolContext]) -> dict:
    """Allowlisted gate features, their coverage, and the ONLY thresholds you may use (training quantiles)."""
    return ctx.deps.feature_grid()


def test_gate_train(ctx: RunContext[ToolContext], conditions: list[ThresholdCondition], allocation_when_true: float,
                    allocation_when_false: float, policy_id: str) -> dict:
    """Evaluate a threshold gate on the TRAIN split only. conditions: 1-2 items of
    {"feature": str, "op": "<=" or ">", "threshold": float}; thresholds must come from feature_grid.
    Allocations must be 0.0, 0.5 or 1.0. Every call is logged and counts against a fixed budget."""
    _log(f"  tool call: test_gate_train {policy_id}")
    spec = {"policy_id": f"agent::{policy_id}", "family": "threshold_gate",
            "conditions": [c.model_dump() if isinstance(c, ThresholdCondition) else c for c in conditions],
            "allocation_when_true": allocation_when_true, "allocation_when_false": allocation_when_false,
            "thresholds_selected_on": "train"}
    return _retry_on_bad_args(ctx.deps.test_gate_train)(spec)


def lookup_evidence(ctx: RunContext[ToolContext], evidence_id: str) -> dict:
    """Return a stored tool output by its evidence_id."""
    if evidence_id not in ctx.deps.store:
        return {"error": f"unknown evidence id {evidence_id}"}
    return ctx.deps.store.get(evidence_id).model_dump(mode="json")


def trial_log(ctx: RunContext[ToolContext]) -> list[dict]:
    """Every policy attempted so far (including refused ones), with train and arbiter validation results."""
    return [t.model_dump() for t in ctx.deps.trials]


# ------------------------------------------------------------------ agents

DIAGNOSTIC_INSTRUCTIONS = """You are a quantitative research analyst supervising an EXISTING trading strategy that must not be changed.
Find WHEN it works and when it fails, using TRAIN data: regime_performance and cost_attribution; news_context only as context.
Rules: every hypothesis cites evidence_id values returned by tools; its conditions must be regime buckets exactly as written in
regime_performance rows (e.g. 'vol_regime=high'); any number you write must be copied from the cited tool output; treat buckets
with fewer than 20 trades or confidence intervals spanning zero as weak; say what would falsify each hypothesis; news
co-occurrence is not causation. Validation and test periods are not available to you."""

PROPOSER_INSTRUCTIONS = f"""You propose SUPERVISORY gates for an unchanged strategy: when to run it at full, half or zero size.
Only the threshold_gate family with 1-2 conditions on these features: {list(GATE_FEATURES)}; ops '<=' or '>';
allocations in {list(ALLOCATIONS)}; thresholds MUST be values returned by feature_grid. You may evaluate candidates with
test_gate_train (TRAIN only, limited budget, every attempt is logged and disclosed). Use unique proposal ids, base each
proposal on the given hypotheses, cite evidence ids, and state a falsification test. Prefer fewer, simpler gates.
Code, not you, will evaluate your proposals on validation and pick at most one for the frozen test."""

CRITIC_INSTRUCTIONS = """You are an independent critic. For each proposed gate, look for: look-ahead or leakage, overfitting (many
trials, effects only in train, validation contradicting train), fragile sample sizes, a gate that is almost always on or off
(see allocation_mix), and counterexamples. Use trial_log (it includes the arbiter's validation runs) and lookup_evidence.
Critique every proposal exactly once and cite that gate's own evaluation evidence id. You cannot change thresholds.
Verdict 'approve_for_frozen_test' only if the validation evidence supports it."""


def _check(problems: list[str]) -> None:
    if problems:
        _log("  validator rejected output: " + "; ".join(problems)[:300])
        raise ModelRetry("; ".join(problems))


def _diagnostic_agent(model) -> Agent:
    agent = Agent(model, output_type=DiagnosticReport, deps_type=ToolContext, instructions=DIAGNOSTIC_INSTRUCTIONS,
                  tools=[regime_performance, cost_attribution, news_context], retries=3, defer_model_check=True)

    @agent.output_validator
    def _v(ctx: RunContext[ToolContext], out: DiagnosticReport) -> DiagnosticReport:
        _check(verify_diagnostic(ctx.deps, out))
        return out

    return agent


def _proposer_agent(model, hypothesis_ids: set[str]) -> Agent:
    agent = Agent(model, output_type=ProposalSet, deps_type=ToolContext, instructions=PROPOSER_INSTRUCTIONS,
                  tools=[feature_grid, regime_performance, test_gate_train], retries=3, defer_model_check=True)

    @agent.output_validator
    def _v(ctx: RunContext[ToolContext], out: ProposalSet) -> ProposalSet:
        _check(verify_proposals(ctx.deps, out, hypothesis_ids))
        return out

    return agent


def _critic_agent(model, proposals: ProposalSet) -> Agent:
    agent = Agent(model, output_type=CritiqueSet, deps_type=ToolContext, instructions=CRITIC_INSTRUCTIONS,
                  tools=[trial_log, lookup_evidence], retries=3, defer_model_check=True)

    @agent.output_validator
    def _v(ctx: RunContext[ToolContext], out: CritiqueSet) -> CritiqueSet:
        _check(verify_critiques(ctx.deps, out, proposals))
        return out

    return agent


def run_diagnostic(ctx: ToolContext, model) -> DiagnosticReport:
    prompt = f"Strategy {ctx.experiment.strategy_id} (version {ctx.experiment.strategy_version}). Diagnose where it works and fails."
    return _run(_diagnostic_agent(model), prompt, ctx, "diagnostic")


def run_proposer(ctx: ToolContext, model, diagnostic: DiagnosticReport) -> ProposalSet:
    ids = {h.hypothesis_id for h in diagnostic.hypotheses}
    prompt = "Hypotheses:\n" + json.dumps([h.model_dump() for h in diagnostic.hypotheses], indent=1)
    return _run(_proposer_agent(model, ids), prompt, ctx, "proposer")


def run_critic(ctx: ToolContext, model, proposals: ProposalSet) -> CritiqueSet:
    payload = [{**p.model_dump(), "spec_hash": spec_hash(p.to_policy_spec())} for p in proposals.proposals]
    prompt = "Proposals to critique:\n" + json.dumps(payload, indent=1)
    return _run(_critic_agent(model, proposals), prompt, ctx, "critic")
