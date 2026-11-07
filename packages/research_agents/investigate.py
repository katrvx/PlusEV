"""`investigate(experiment_id) -> InvestigationReport` (AGENTS.md Lane B output interface).

Flow:
  1. diagnostic agent       -> ranked hypotheses with evidence ids        (train + validation regime stats)
  2. gate proposer          -> allowlisted gates, tested on TRAIN only     (budgeted, every attempt logged)
  3. arbiter (code)         -> evaluates every candidate on VALIDATION, plus the simple rule and the
                               LightGBM gate as competitors under identical conditions
  4. critic agent           -> leakage / overfit / fragility review with evidence ids
  5. arbiter (code)         -> pre-registered acceptance rule decides which candidates go to the
                               ONE frozen test; the LLM's confidence cannot override it
The sealed test split is never touched here. Lane A runs the frozen test.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from . import fallback
from .agents import configured_model, run_critic, run_diagnostic, run_proposer
from .models import CritiqueSet, InvestigationReport, PolicyCandidate
from .tools import ToolContext

# Pre-registered rule for which candidates go to the ONE frozen test (stated before any run):
#  - candidate improves VALIDATION net return vs always-on after costs (delta > 0)
#  - and the critic approved it, and it is not fragile.
# Going to the test is not a claim of success: validation CIs are wide, and whether the
# improvement is real is decided by the sealed test (and reported with its CI) by Lane A.


Loader = Callable[[str], tuple]   # experiment_id -> (ExperimentResult, GateRunner, train_quantiles, news_store|None, lgbm|None)


def _fixture_loader(experiment_id: str):
    from fixtures.lane_a_stub import build
    exp, runner, tq, _df, lgbm = build()
    return exp, runner, tq, None, lgbm


def investigate(experiment_id: str, loader: Loader = _fixture_loader, model: str | None = None,
                force_fallback: bool = False) -> InvestigationReport:
    exp, runner, train_quantiles, news, lgbm = loader(experiment_id)
    ctx = ToolContext(experiment=exp, gate_runner=runner, news=news, train_quantiles=train_quantiles)
    model = None if force_fallback else (model or configured_model())
    mode = "llm" if model else "deterministic_fallback"

    # 1-2. hypotheses and proposals
    if model:
        diagnostic = run_diagnostic(ctx, model)
        proposals = run_proposer(ctx, model, diagnostic)
    else:
        diagnostic = fallback.diagnose(ctx)
        proposals = fallback.propose(ctx, diagnostic)

    # 3. arbiter evaluates every candidate on validation, with competitors
    competitors = []
    for p in proposals.proposals:
        ctx.test_gate_train(p.to_policy_spec(), split="validation", source="agent")
    if lgbm is not None:
        ctx.test_gate_train(lgbm.spec(), split="validation", source="meta_model")
        competitors.append(("meta_model", lgbm.spec()))

    # 4. critic
    critiques: CritiqueSet = run_critic(ctx, model, proposals) if model else fallback.critique(ctx, proposals)
    crit = {c.proposal_id: c for c in critiques.critiques}

    # 5. pre-registered acceptance
    val = {t.policy_id: t for t in ctx.trials if t.split == "validation" and t.status == "evaluated"}
    candidates = []
    for p in proposals.proposals:
        pid = f"agent::{p.proposal_id}"
        t, c = val.get(pid), crit.get(p.proposal_id)
        reasons, ok = [], True
        if t is None:
            ok = False
            reasons.append("no validation evaluation")
        else:
            reasons.append(f"validation delta vs always-on {t.delta_net_return_vs_always_on:+.4f}, CI {t.ci_delta}")
            if t.delta_net_return_vs_always_on <= 0:
                ok = False
                reasons.append("does not improve validation after costs")
            if t.ci_delta and t.ci_delta[0] <= 0:
                reasons.append("note: validation CI includes zero; the frozen test decides")
        if c is None or c.verdict != "approve_for_frozen_test":
            ok = False
            reasons.append(f"critic verdict: {c.verdict if c else 'missing'}")
        if c and c.fragile_samples:
            ok = False
            reasons.append("fragile: " + "; ".join(c.fragile_samples))
        candidates.append(PolicyCandidate(policy_id=pid, source="agent", policy_spec=p.to_policy_spec(),
                                          status="accepted_for_frozen_test" if ok else "rejected", reasons=reasons,
                                          evidence_ids=[e for e in [*(p.evidence_ids), t.evidence_id if t else None] if e]))
    for source, spec in competitors:
        t = val.get(spec["policy_id"])
        candidates.append(PolicyCandidate(policy_id=spec["policy_id"], source=source, policy_spec=spec,
                                          status="accepted_for_frozen_test", reasons=["competitor: always carried to the frozen test for comparison",
                                                                                        f"validation delta {t.delta_net_return_vs_always_on:+.4f}" if t else "not evaluated"],
                                          evidence_ids=[t.evidence_id] if t and t.evidence_id else []))

    n_tried = sum(t.status != "refused" for t in ctx.trials)
    limitations = [
        f"{n_tried} policies evaluated (including refused attempts: {len(ctx.trials)} logged); results are subject to multiple-comparison risk.",
        "Validation was used for acceptance; only the frozen test is unbiased.",
        "Regime effects are associations under lagged features; not causal.",
    ]
    if mode == "deterministic_fallback":
        limitations.append("Agents ran in deterministic fallback mode (no LLM configured).")
    if not exp.coverage.get("news_sentiment", 0) >= 0.9:
        limitations.append(f"news_sentiment coverage {exp.coverage.get('news_sentiment', 0):.0%}: not allowed in gates; market-only gating.")

    return InvestigationReport(
        experiment_id=exp.experiment_id, strategy_id=exp.strategy_id, generated_at=datetime.now(timezone.utc),
        agent_mode=mode, model_id=model, diagnostic=diagnostic, proposals=proposals.proposals, critiques=critiques.critiques,
        trial_log=ctx.trials, candidates=candidates,
        test_requests=["Lane A: run always_on, cash, simple_rule and every accepted candidate ONCE on the sealed test split, same costs."],
        limitations=limitations, evidence=ctx.store.all(), n_policies_tried=n_tried, holdout_accessed=ctx.holdout_accessed,
    )
