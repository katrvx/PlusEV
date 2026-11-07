"""`investigate(experiment_id) -> InvestigationReport` (AGENTS.md Lane B output interface).

Flow:
  1. diagnostic agent  -> ranked hypotheses from TRAIN regime stats, each claim verified against evidence
  2. gate proposer     -> allowlisted gates, tested on TRAIN only (own budget, every attempt logged)
  3. arbiter (code)    -> evaluates every proposal on VALIDATION, plus two competitors under identical
                          conditions: the simple rule baseline and the LightGBM gate
  4. critic agent      -> reviews each gate against its own train + validation evidence
  5. arbiter (code)    -> PRE-REGISTERED rule: among proposals with validation delta > 0, critic approval
                          and a non-degenerate allocation mix, the ONE with the highest validation delta
                          becomes the agent champion. Only that champion and the competitors go to the
                          single frozen test. No champion -> verdict INCONCLUSIVE.
Any LLM failure (bad output after retries, tool errors, API errors) falls back to the deterministic
agents for that stage and is recorded in `agent_failures`. The test split is never touched here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from packages.meta_policy import rule_gate_spec

from . import fallback
from .agents import (configured_model, model_name, run_critic, run_diagnostic, run_proposer,
                     verify_critiques, verify_diagnostic, verify_proposals)
from .models import CritiqueSet, InvestigationReport, PolicyCandidate, ProposalSet
from .tools import ToolContext, spec_hash

DEGENERATE_SHARE = fallback.DEGENERATE_SHARE

Loader = Callable[[str], tuple]   # experiment_id -> (ExperimentResult, GateRunner, train_quantiles, NewsStore|None, LGBMGate|None)


def _fixture_loader(experiment_id: str):
    from fixtures.lane_a_stub import build
    exp, runner, tq, _df, lgbm = build()
    return exp, runner, tq, None, lgbm


def _stage(name, llm_call, fallback_call, model, failures: list[str]):
    if model is not None:
        try:
            return llm_call(), True
        except Exception as exc:  # noqa: BLE001 - any LLM failure must degrade gracefully, and be disclosed
            failures.append(f"{name}: {type(exc).__name__}: {str(exc)[:300]} -> deterministic fallback used")
    return fallback_call(), False


def investigate(experiment_id: str, loader: Loader = _fixture_loader, model=None,
                force_fallback: bool = False) -> InvestigationReport:
    exp, runner, train_quantiles, news, lgbm = loader(experiment_id)
    ctx = ToolContext(experiment=exp, gate_runner=runner, news=news, train_quantiles=train_quantiles)
    model = None if force_fallback else (model or configured_model())
    failures: list[str] = []
    limitations: list[str] = []
    used_llm = []

    # 1. diagnosis
    diagnostic, ok = _stage("diagnostic", lambda: run_diagnostic(ctx, model), lambda: fallback.diagnose(ctx), model, failures)
    used_llm.append(ok)
    if not ok:
        problems = verify_diagnostic(ctx, diagnostic)
        if problems:
            limitations.append("fallback diagnostic verification issues: " + "; ".join(problems))

    # 2. proposals (train only)
    hyp_ids = {h.hypothesis_id for h in diagnostic.hypotheses}
    proposals, ok = _stage("proposer", lambda: run_proposer(ctx, model, diagnostic), lambda: fallback.propose(ctx, diagnostic), model, failures)
    used_llm.append(ok)
    problems = verify_proposals(ctx, proposals, hyp_ids)
    if problems:   # only possible on the fallback path; drop offending proposals rather than evaluate them
        bad = {msg.split(":")[0].split(" ")[0] for msg in problems}
        limitations.append("proposals dropped by verification: " + "; ".join(problems))
        proposals = ProposalSet(proposals=[p for p in proposals.proposals if p.proposal_id not in bad])

    # 3. arbiter: validation runs for every proposal and both competitors (never budgeted)
    for p in proposals.proposals:
        ctx.arbiter_evaluate(p.to_policy_spec(), "validation", source="arbiter")
    rule = rule_gate_spec(train_quantiles)
    ctx.arbiter_evaluate(rule, "validation", source="rule_baseline")
    competitors = [("rule_baseline", rule)]
    if lgbm is not None:
        ctx.arbiter_evaluate(lgbm.spec(), "validation", source="meta_model")
        competitors.append(("meta_model", lgbm.spec()))

    def val_trial(spec):
        h = spec_hash(spec)
        return next((t for t in ctx.trials if t.spec_hash == h and t.split == "validation" and t.status == "evaluated"), None)

    rule_t = val_trial(rule)
    rule_delta = rule_t.delta_net_return_vs_always_on if rule_t else None

    # 4. critic
    critiques = CritiqueSet.model_construct(critiques=[])
    if proposals.proposals:
        critiques, ok = _stage("critic", lambda: run_critic(ctx, model, proposals), lambda: fallback.critique(ctx, proposals), model, failures)
        used_llm.append(ok)
        problems = verify_critiques(ctx, critiques, proposals)
        if problems:
            limitations.append("critic verification issues: " + "; ".join(problems))
    crit = {c.proposal_id: c for c in critiques.critiques}

    # 5. pre-registered selection of at most ONE agent champion
    rows = []
    for p in proposals.proposals:
        spec = p.to_policy_spec()
        t, c = val_trial(spec), crit.get(p.proposal_id)
        reasons, eligible = [], True
        mix = t.allocation_mix if t else {}
        if t is None:
            eligible = False
            reasons.append("no validation evaluation")
        else:
            reasons.append(f"validation delta vs always-on {t.delta_net_return_vs_always_on:+.4f}, 90% CI {t.ci_delta}")
            if t.delta_net_return_vs_always_on <= 0:
                eligible = False
                reasons.append("does not improve validation after costs")
            if t.ci_delta and t.ci_delta[0] <= 0:
                reasons.append("validation CI includes zero; the frozen test decides")
            if mix and max(mix.values()) >= DEGENERATE_SHARE:
                eligible = False
                reasons.append(f"degenerate: one multiplier on {max(mix.values()):.0%} of validation decisions")
        if c is None or c.verdict != "approve_for_frozen_test":
            eligible = False
            reasons.append(f"critic verdict: {c.verdict if c else 'missing'}")
        if c and c.fragile_samples:
            eligible = False
            reasons.append("fragile: " + "; ".join(c.fragile_samples))
        rows.append((p, spec, t, c, eligible, reasons))

    eligible_rows = [r for r in rows if r[4]]
    champion = max(eligible_rows, key=lambda r: r[2].delta_net_return_vs_always_on) if eligible_rows else None
    candidates = []
    for p, spec, t, c, eligible, reasons in rows:
        is_champ = champion is not None and p is champion[0]
        if eligible and not is_champ:
            reasons = reasons + ["eligible but not selected: only the highest-validation-delta agent policy goes to the frozen test"]
        candidates.append(PolicyCandidate(
            policy_id=spec["policy_id"], spec_hash=spec_hash(spec), source="agent",
            role="agent_champion" if is_champ else "agent_not_selected",
            policy_spec=spec, status="accepted_for_frozen_test" if is_champ else "rejected",
            validation_delta_vs_always_on=t.delta_net_return_vs_always_on if t else None,
            validation_ci=t.ci_delta if t else None,
            validation_delta_vs_simple_rule=(t.delta_net_return_vs_always_on - rule_delta) if (t and rule_delta is not None) else None,
            allocation_mix=t.allocation_mix if t else {}, reasons=reasons,
            evidence_ids=[e for e in [*p.evidence_ids, t.evidence_id if t else None, *(c.evidence_ids if c else [])] if e],
        ))
    for source, spec in competitors:
        t = val_trial(spec)
        reasons = ["competitor: always carried to the frozen test for comparison"]
        if t:
            reasons.append(f"validation delta vs always-on {t.delta_net_return_vs_always_on:+.4f}, 90% CI {t.ci_delta}")
            if t.allocation_mix and max(t.allocation_mix.values()) >= DEGENERATE_SHARE:
                reasons.append(f"degenerate: one multiplier on {max(t.allocation_mix.values()):.0%} of validation decisions")
        else:
            reasons.append("validation evaluation failed")
        candidates.append(PolicyCandidate(
            policy_id=spec["policy_id"], spec_hash=spec_hash(spec), source=source, role="competitor", policy_spec=spec,
            status="competitor", validation_delta_vs_always_on=t.delta_net_return_vs_always_on if t else None,
            validation_ci=t.ci_delta if t else None,
            validation_delta_vs_simple_rule=(t.delta_net_return_vs_always_on - rule_delta) if (t and rule_delta is not None) else None,
            allocation_mix=t.allocation_mix if t else {}, reasons=reasons, evidence_ids=[t.evidence_id] if t and t.evidence_id else [],
        ))

    verdict = "candidate_for_frozen_test" if champion else "INCONCLUSIVE"
    champ_id = champion[1]["policy_id"] if champion else None
    agent_specs = {t.spec_hash for t in ctx.trials if t.source == "agent" and t.spec_hash}
    all_specs = {t.spec_hash for t in ctx.trials if t.status == "evaluated" and t.spec_hash}
    limitations += [
        f"{len(agent_specs)} distinct agent gate specs attempted ({ctx.agent_tests_used()} agent train tests logged, refused ones included); "
        f"{len(all_specs)} distinct policies evaluated in total. Multiple-comparison risk applies to train and validation results.",
        "Validation selected the single agent champion; only the frozen test is an unbiased estimate.",
        "Regime effects are associations under lagged features, not causal.",
        "Returns convention: compounded simple returns after costs; deltas and CIs use the same convention (Lane A).",
    ]
    if verdict == "INCONCLUSIVE":
        limitations.append("No agent policy met the pre-registered rule; the agent layer adds nothing here. Competitors are still reported.")
    if not any(used_llm) or model is None:
        limitations.append("Agents ran in deterministic fallback mode (no LLM).")
    if exp.coverage.get("news_sentiment", 0) < 0.9:
        limitations.append(f"news_sentiment coverage {exp.coverage.get('news_sentiment', 0):.0%}: not allowed in gates; market-only gating.")
    if news is None:
        limitations.append("No news source configured: no news context, no market-only vs market+news ablation.")

    mode = "deterministic_fallback" if (model is None or not any(used_llm)) else ("llm" if all(used_llm) else "llm_with_fallback")
    to_test = [c.policy_id for c in candidates if c.status in ("accepted_for_frozen_test", "competitor")]
    return InvestigationReport(
        experiment_id=exp.experiment_id, strategy_id=exp.strategy_id, generated_at=datetime.now(timezone.utc),
        agent_mode=mode, model_id=model_name(model), agent_failures=failures, verdict=verdict, champion_policy_id=champ_id,
        diagnostic=diagnostic, proposals=proposals.proposals, critiques=critiques.critiques, trial_log=ctx.trials,
        candidates=candidates,
        test_requests=[f"Lane A: run ONCE on the sealed test split with identical costs: always_on, cash, {', '.join(to_test)}. "
                       "Report each vs always_on and vs the simple rule, with CIs. Do not change any policy after seeing the result."],
        limitations=limitations, evidence=ctx.store.all(), n_distinct_agent_policies=len(agent_specs),
        n_policies_tried=len(all_specs), holdout_accessed=ctx.holdout_accessed,
    )
