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

from pydantic import ValidationError
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.usage import UsageLimits

from .allowlist import ALLOCATIONS, GATE_FEATURES, check_gate
from .models import ContextReport, CritiqueSet, DiagnosticReport, ProposalSet, ThresholdCondition
from .tools import HoldoutAccessError, ToolContext, spec_hash

MODEL_ENV = "KOK_AGENT_MODEL"

# Hard bounds so a slow or looping model can never hang the run (any breach -> fallback, disclosed).
STAGE_TIMEOUT_S = float(os.environ.get("KOK_STAGE_TIMEOUT", "400"))     # whole agent stage
REQUEST_TIMEOUT_S = float(os.environ.get("KOK_REQUEST_TIMEOUT", "180"))  # single model request (strong models can take >90s)
MAX_REQUESTS = int(os.environ.get("KOK_MAX_REQUESTS", "15"))            # model round-trips per stage


def _log(msg: str) -> None:
    print(f"[agents] {msg}", file=sys.stderr, flush=True)


def _run(agent: Agent, prompt: str, ctx: ToolContext, stage: str):
    _log(f"{stage}: start (timeout {STAGE_TIMEOUT_S:.0f}s, max {MAX_REQUESTS} model requests)")
    t0 = time.monotonic()
    result = agent.run_sync(prompt, deps=ctx, timeout=STAGE_TIMEOUT_S,
                            usage_limits=UsageLimits(request_limit=MAX_REQUESTS),
                            model_settings={"timeout": REQUEST_TIMEOUT_S, "temperature": 0.2})
    try:
        u = result.usage
        if not hasattr(u, "requests"):   # older pydantic-ai: usage() was a method
            u = u()
        stats = f", {u.requests} requests, {u.total_tokens} tokens"
    except Exception:  # noqa: BLE001 - usage reporting must never discard a successful stage
        stats = ""
    _log(f"{stage}: done in {time.monotonic() - t0:.0f}s{stats}")
    return result.output


def configured_model() -> str | None:
    return os.environ.get(MODEL_ENV) or None


def model_name(model) -> str | None:
    if model is None:
        return None
    return model if isinstance(model, str) else getattr(model, "model_name", type(model).__name__)


# ------------------------------------------------------------------ claim verification lives in verify.py

from .verify import MIN_TRADES, unsupported_numbers, verify_context, verify_critiques, verify_diagnostic, verify_proposals  # noqa: E402,F401


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
    Only the TRAIN period is available to you. Contextual evidence only, never causal proof."""
    try:
        return _retry_on_bad_args(ctx.deps.news_context)(start, end, decision_cutoff, agent=True)
    except HoldoutAccessError as exc:
        ctx.deps.attempt_holdout("news_context")
        return {"error": str(exc)}


def sentiment_episodes(ctx: RunContext[ToolContext]) -> dict:
    """Fear & Greed around the unchanged strategy's 4 worst and 4 best TRAIN weeks: level, 7-day change and
    greed/fear flips in the 3 days before each week, plus train base rates and binomial p-values. Cite its evidence_id."""
    _log("  tool call: sentiment_episodes")
    return ctx.deps.sentiment_context()


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
    token = ctx.deps.enter_tool()
    try:
        return _retry_on_bad_args(ctx.deps.test_gate_train)(spec, stage_token=token)
    finally:
        ctx.deps.exit_tool()


def lookup_evidence(ctx: RunContext[ToolContext], evidence_id: str) -> dict:
    """Return a stored tool output by its evidence_id."""
    if evidence_id not in ctx.deps.store:
        return {"error": f"unknown evidence id {evidence_id}"}
    return ctx.deps.store.get(evidence_id).model_dump(mode="json")


def strategy_health(ctx: RunContext[ToolContext]) -> dict:
    """Bad luck vs broken, computed by code: are the unchanged strategy's validation 14-day results inside its
    train-only range, and which assumptions (exposure, turnover, costs, volatility, regime frequencies) changed
    between train and validation? Returns an evidence_id to cite."""
    return ctx.deps.health or {"error": "strategy health is not available for this loader"}


def trial_log(ctx: RunContext[ToolContext]) -> list[dict]:
    """Every policy attempted so far (including refused ones), with train and arbiter validation results."""
    return [t.model_dump() for t in ctx.deps.trials]


# ------------------------------------------------------------------ agents

DIAGNOSTIC_INSTRUCTIONS = f"""You are a quantitative research analyst supervising an EXISTING trading strategy that must not be changed.
Find WHEN it works and when it fails, using TRAIN data: regime_performance and cost_attribution; news_context only as context.
Rules: every hypothesis cites evidence_id values returned by tools; its conditions must be regime buckets exactly as written in
regime_performance rows (e.g. 'vol_regime=high'); any number you write must be copied from the cited tool output; all confidence intervals are 90%; treat buckets
with fewer than {MIN_TRADES} trades or confidence intervals spanning zero as weak; say what would falsify each hypothesis; news
co-occurrence is not causation. Validation and test periods are not available to you.
Numbers: copy them from the cited tool output and round to 3-4 significant digits (0.3043, -3.54e-05, 5.15%);
rounding is fine, changing digits or computing new numbers is not."""

CONTEXT_INSTRUCTIONS = """You are the context analyst for an EXISTING trading strategy that must not be changed. Call sentiment_episodes
(TRAIN only) and report what market sentiment (Fear & Greed) was doing around the strategy's worst and best weeks:
levels, 7-day changes, and greed/fear flips just before a week started, compared with the train base rates.
Rules: every finding cites the sentiment_episodes evidence_id and names the episode_ids it uses; any number you write is
copied from that output; describe co-occurrence in time only, never a cause ('because', 'caused', 'led to' are rejected);
when a finding reports one of the tallies, set `tally` to its key; strength 'moderate' only for one of the two PRIMARY tallies
(see primary_tallies) with binomial_p_value below 0.05 (four tallies are computed, so the threshold is corrected), otherwise
'weak' or 'none'; with 4 weeks per side say the sample is small. If sentiment does not separate good and bad weeks, say so plainly: that is a valid finding."""

PROPOSER_INSTRUCTIONS = f"""You propose SUPERVISORY gates for an unchanged strategy: when to run it at full, half or zero size.
Only the threshold_gate family with 1-2 conditions on these features: {list(GATE_FEATURES)}; ops '<=' or '>';
allocations in {list(ALLOCATIONS)}; thresholds MUST be values returned by feature_grid. You may evaluate candidates with
test_gate_train (TRAIN only, limited budget, every attempt is logged and disclosed). Use unique proposal ids, base each
proposal on the given hypotheses, cite evidence ids, and state a falsification test. Prefer fewer, simpler gates.
Code, not you, will evaluate your proposals on validation and pick at most one for the frozen test.
Take the direction from THIS strategy's evidence: do not assume an up-trend is good or high volatility is bad; a
mean-reversion strategy can be the opposite of a trend strategy. Trend: momentum_24h (short) vs momentum_7d (longer).
Volatility level: realized_vol_7d, atr_14; volatility change: vol_ratio_24h_7d (above 1 = recent volatility rising vs its
7-day baseline). volume_zscore is a volume proxy, not liquidity (no spread or order-book data exists); say "volume".
fear_greed is daily and usable the next day. A gate that wins only by holding less is not timing: code compares every
proposal with constant half size and with a constant at the same average size.
Numbers: copy them from the cited tool output and round to 3-4 significant digits (0.3043, -3.54e-05, 5.15%);
rounding is fine, changing digits or computing new numbers is not."""

CRITIC_INSTRUCTIONS = """You are an independent critic. For each proposed gate, look for: look-ahead or leakage, overfitting (many
trials, effects only in train, validation contradicting train), fragile sample sizes, a gate that is almost always on or off
(see allocation_mix), and counterexamples. Use trial_log (it includes the arbiter's validation runs) and lookup_evidence.
Critique every proposal exactly once and cite that gate's own evaluation evidence id. You cannot change thresholds.
trial_log also holds the arbiter's walk-forward runs (note 'walk-forward fold k'): the same gate on later TRAIN sub-periods.
Use them to check whether an effect is stable over time; thresholds were chosen on all of train, so they are not unseen data.
strategy_health says whether the unchanged strategy's validation result is ordinary bad luck or outside its training
range, and which assumptions changed (e.g. a regime that became much more frequent). A gate whose feature's regime
shifted between train and validation may only look good or bad because of that shift: say so.
All confidence intervals are 90%. Put only issues that should BLOCK the frozen test in fragile_samples; non-blocking
remarks go in observations. Verdict 'approve_for_frozen_test' only if the validation evidence supports it.
Numbers: copy them from the cited tool output and round to 3-4 significant digits (0.3043, -3.54e-05, 5.15%);
rounding is fine, changing digits or computing new numbers is not."""


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


def _context_agent(model) -> Agent:
    agent = Agent(model, output_type=ContextReport, deps_type=ToolContext, instructions=CONTEXT_INSTRUCTIONS,
                  tools=[sentiment_episodes], retries=3, defer_model_check=True)

    @agent.output_validator
    def _v(ctx: RunContext[ToolContext], out: ContextReport) -> ContextReport:
        _check(verify_context(ctx.deps, out))
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
                  tools=[trial_log, lookup_evidence, strategy_health], retries=3, defer_model_check=True)

    @agent.output_validator
    def _v(ctx: RunContext[ToolContext], out: CritiqueSet) -> CritiqueSet:
        _check(verify_critiques(ctx.deps, out, proposals))
        return out

    return agent


def run_diagnostic(ctx: ToolContext, model) -> DiagnosticReport:
    prompt = f"Strategy {ctx.experiment.strategy_id} (version {ctx.experiment.strategy_version}). Diagnose where it works and fails."
    return _run(_diagnostic_agent(model), prompt, ctx, "diagnostic")


def run_context(ctx: ToolContext, model) -> ContextReport:
    prompt = f"Strategy {ctx.experiment.strategy_id}. What was market sentiment doing around its best and worst train weeks?"
    return _run(_context_agent(model), prompt, ctx, "context")


def run_proposer(ctx: ToolContext, model, diagnostic: DiagnosticReport, context: ContextReport | None = None) -> ProposalSet:
    ids = {h.hypothesis_id for h in diagnostic.hypotheses}
    prompt = "Hypotheses:\n" + json.dumps([h.model_dump() for h in diagnostic.hypotheses], indent=1)
    if context and context.findings:
        prompt += ("\n\nSentiment context (co-occurrence only, not causes; base proposals on the hypotheses above):\n"
                   + json.dumps([{"statement": f.statement, "strength": f.strength} for f in context.findings], indent=1))
    return _run(_proposer_agent(model, ids), prompt, ctx, "proposer")


def run_critic(ctx: ToolContext, model, proposals: ProposalSet) -> CritiqueSet:
    payload = [{**p.model_dump(), "spec_hash": spec_hash(p.to_policy_spec())} for p in proposals.proposals]
    prompt = "Proposals to critique:\n" + json.dumps(payload, indent=1)
    return _run(_critic_agent(model, proposals), prompt, ctx, "critic")
