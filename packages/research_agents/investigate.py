"""`investigate(experiment_id) -> InvestigationReport` (AGENTS.md Lane B output interface).

Flow:
  1. diagnostic agent  -> ranked hypotheses from TRAIN regime stats; every text field checked against evidence
  2. gate proposer     -> allowlisted gates, tested on TRAIN only (own budget, every attempt logged)
  3. arbiter (code)    -> evaluates every proposal on VALIDATION, plus competitors under identical conditions:
                          the simple rule baseline, the LightGBM gate and (when the loader has one) Lane A's
                          train-selected regime filter; always-on and cash are the references.
                          Then all of them on Lane A's expanding TRAIN folds (stability check, not a veto)
  4. critic agent      -> reviews each gate against its own train + validation evidence
  5. arbiter (code)    -> PRE-REGISTERED RULE (written before any run):
       an agent proposal is ELIGIBLE iff, on validation,
         (a) its delta vs always-on is finite and > 0, and its CI is finite,
         (b) it beats cash: its own net return is > 0,
         (c) its in-position allocation mix is not degenerate (no multiplier on >= 95% of in-position bars),
         (d) the critic did not veto it (verdict 'reject'/'needs_change', or any BLOCKING fragile_samples entry).
       The eligible proposal with the highest validation delta vs always-on is the single agent CHAMPION.
       verdict = 'candidate_for_frozen_test' if there is a champion, else 'INCONCLUSIVE' (the agent layer adds
       nothing here). The strategy-level KEEP / ACTIVATE / KILL decision is Lane A's arbiter's
       (docs/INTEGRATION_DECISIONS.md); this report gives it the cash and always-on references it needs.
Any LLM failure falls back to the deterministic agent for that stage and is recorded in `agent_failures`.
Tool calls that finish after their stage timed out are logged (status 'error', note 'abandoned: ...') and disclosed. The test split
is never touched here.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from typing import Callable

from packages.meta_policy import LGBM_UNAVAILABLE, rule_gate_spec

from . import fallback
from .agents import configured_model, model_name, run_context, run_critic, run_diagnostic, run_proposer
from .models import CritiqueSet, InvestigationReport, PolicyCandidate, ProposalSet
from .health import strategy_health
from .tools import ToolContext, spec_hash
from .verify import verify_context, verify_critiques, verify_diagnostic, verify_proposals

DEGENERATE_SHARE = fallback.DEGENERATE_SHARE

Loader = Callable[[str], tuple]   # experiment_id -> (ExperimentResult, GateRunner, train_quantiles, NewsStore|None, LGBMGate|None)


def _fixture_loader(experiment_id: str):
    from fixtures.lane_a_stub import build
    exp, runner, tq, _df, lgbm = build()
    return exp, runner, tq, None, lgbm


def _finite(*xs) -> bool:
    return all(isinstance(x, (int, float)) and math.isfinite(x) for x in xs)


def _stage(name, llm_call, fallback_call, model, failures: list[str], ctx: ToolContext):
    if model is not None:
        try:
            return llm_call(), True
        except Exception as exc:  # noqa: BLE001 - any LLM failure must degrade gracefully, and be disclosed
            msg = f"{name}: {type(exc).__name__}: {str(exc)[:300]} -> deterministic fallback used"
            print(f"[agents] {msg}", file=sys.stderr, flush=True)
            failures.append(msg)
        finally:
            ctx.close_stage()   # any agent tool call still running from this stage is now 'abandoned'
    return fallback_call(), False


def investigate(experiment_id: str, loader: Loader = _fixture_loader, model=None,
                force_fallback: bool = False) -> InvestigationReport:
    exp, runner, train_quantiles, news, lgbm = loader(experiment_id)
    ctx = ToolContext(experiment=exp, gate_runner=runner, news=news, train_quantiles=train_quantiles)
    model = None if force_fallback else (model or configured_model())
    failures: list[str] = []
    limitations: list[str] = []
    used_llm: list[bool] = []
    agent_tests_before_failure = 0

    # 1. diagnosis
    diagnostic, ok = _stage("diagnostic", lambda: run_diagnostic(ctx, model), lambda: fallback.diagnose(ctx), model, failures, ctx)
    used_llm.append(ok)
    if not ok:
        problems = verify_diagnostic(ctx, diagnostic)
        if problems:
            limitations.append("fallback diagnostic verification issues: " + "; ".join(problems))

    # 1b. context (agent 4): sentiment around the best/worst train weeks; skipped (and disclosed) without a series
    context = None
    try:
        pre = ctx.sentiment_context()
    except Exception as exc:  # noqa: BLE001 - bad loader data must not crash the investigation
        pre = {"error": f"{type(exc).__name__}: {exc}"}
    if "error" in pre:
        limitations.append(f"Context agent skipped: {pre['error']}.")
    else:
        context, ok = _stage("context", lambda: run_context(ctx, model), lambda: fallback.context(ctx), model, failures, ctx)
        used_llm.append(ok)
        if not ok:
            problems = verify_context(ctx, context)
            if problems:
                limitations.append("fallback context verification issues: " + "; ".join(problems))

    # 2. proposals (train only)
    hyp_ids = {h.hypothesis_id for h in diagnostic.hypotheses}
    tests_at_start = ctx.agent_tests_used()
    proposals, ok = _stage("proposer", lambda: run_proposer(ctx, model, diagnostic, context), lambda: fallback.propose(ctx, diagnostic),
                           model, failures, ctx)
    used_llm.append(ok)
    if not ok and model is not None:
        agent_tests_before_failure = ctx.agent_tests_used() - tests_at_start
    problems = verify_proposals(ctx, proposals, hyp_ids)
    if problems:   # only possible on the fallback path; drop offending proposals rather than evaluate them
        bad = {msg.split(":")[0].split(" ")[0] for msg in problems}
        limitations.append("proposals dropped by verification: " + "; ".join(problems))
        proposals = ProposalSet(proposals=[p for p in proposals.proposals if p.proposal_id not in bad])

    # 3. arbiter: validation runs for every proposal and the competitors (never budgeted)
    for p in proposals.proposals:
        ctx.arbiter_evaluate(p.to_policy_spec(), "validation", source="arbiter")
    # Lane A's runner carries the rule it actually scored. The quantile reconstruction
    # is only for the synthetic stand-in, which has no runner.rule_spec.
    rule = getattr(runner, "rule_spec", None) or rule_gate_spec(ctx.train_quantiles)
    rule_out = ctx.arbiter_evaluate(rule, "validation", source="rule_baseline")
    competitors = [("rule_baseline", rule)]
    if lgbm is not None:
        ctx.arbiter_evaluate(lgbm.spec(), "validation", source="meta_model")
        competitors.append(("meta_model", lgbm.spec()))
    # Lane A's train-selected regime filter: the judges' question is whether the agent beats it.
    # Like the simple rule it is a reference, not a veto (the selection rule below is pre-registered).
    regime = getattr(runner, "regime_spec", None)
    regime_note = None
    if regime and regime.get("family") == "regime_gate" and not regime.get("flat_buckets") and not regime.get("full_buckets") \
            and regime.get("allocation_else", 1.0) == 1.0:
        # no train bucket was selected: the filter IS always-on; comparing against it would just repeat always-on
        regime_note = f"Lane A regime filter selected no train buckets, so it equals always-on ({regime.get('summary', '')}); not a separate competitor"
        regime = None
    if regime:
        ctx.arbiter_evaluate(regime, "validation", source="rule_baseline")
        competitors.append(("rule_baseline", regime))
    # Constant half size: a gate that mostly halves exposure must beat simply holding half (R4-F3). Reference, not a veto.
    half = {"policy_id": "rule::half_size_constant", "family": "threshold_gate",
            "conditions": [{"feature": "realized_vol_7d", "op": ">", "threshold": -1.0}],   # always true: vol >= 0
            "allocation_when_true": 0.5, "allocation_when_false": 0.5, "thresholds_selected_on": "none (constant)",
            "summary": "Always half size: the exposure-only baseline."}
    ctx.arbiter_evaluate(half, "validation", source="rule_baseline")
    competitors.append(("rule_baseline", half))

    # 3b. walk-forward: the same frozen specs on Lane A's expanding TRAIN folds (stability, not unseen data)
    # The fitted LightGBM saw all of train (fit + calibration), so scoring it on train folds is in-sample.
    # For it we report Lane A's own walk-forward, which refits the model before each fold.
    fold_runs, refit_folds = {}, {}
    for src, spec in [("arbiter", p.to_policy_spec()) for p in proposals.proposals] + competitors:
        if src == "meta_model":
            refit_folds[spec_hash(spec)] = [w.delta_net_return_vs_always_on for w in getattr(exp, "walk_forward", []) or []]
        else:
            fold_runs[spec_hash(spec)] = ctx.arbiter_folds(spec, source=src)

    def fold_line(spec):
        h = spec_hash(spec)
        refit = h in refit_folds
        deltas = refit_folds[h] if refit else [f["evaluation"]["delta_net_return_vs_always_on"] for f in fold_runs.get(h, [])]
        deltas = [d for d in deltas if _finite(d)]
        if not deltas:
            return None
        wins = sum(d > 0 for d in deltas)
        what = "Lane A refit walk-forward (model refit before each train fold)" if refit else "walk-forward on train folds"
        return (f"{what}: beats always-on on {wins}/{len(deltas)} "
                f"({', '.join(f'{d:+.4f}' for d in deltas)}); stability check, not a veto")

    def val_trial(spec):
        h = spec_hash(spec)
        return next((t for t in ctx.trials if t.spec_hash == h and t.split == "validation" and t.status == "evaluated"), None)

    rule_t = val_trial(rule)
    rule_delta = rule_t.delta_net_return_vs_always_on if rule_t else None
    regime_t = val_trial(regime) if regime else None
    regime_delta = regime_t.delta_net_return_vs_always_on if regime_t else None
    half_t = val_trial(half)
    half_delta = half_t.delta_net_return_vs_always_on if half_t else None
    always_on = rule_out.get("evaluation", {}).get("always_on", {}) if isinstance(rule_out, dict) else {}

    # 3c. bad luck vs broken (code; reads validation of the unchanged strategy, so the critic sees it, agents 1-2 do not)
    health = strategy_health(ctx.experiment)
    if health:
        ctx.health = {**health, "evidence_id": ctx.store.add("strategy_health", {}, health)}

    # 4. critic
    critiques = CritiqueSet.model_construct(critiques=[])
    if proposals.proposals:
        critiques, ok = _stage("critic", lambda: run_critic(ctx, model, proposals), lambda: fallback.critique(ctx, proposals),
                               model, failures, ctx)
        used_llm.append(ok)
        problems = verify_critiques(ctx, critiques, proposals)
        if problems:
            limitations.append("critic verification issues: " + "; ".join(problems))
    crit = {c.proposal_id: c for c in critiques.critiques}

    # 5. pre-registered selection
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
            d, ci, net = t.delta_net_return_vs_always_on, t.ci_delta, t.net_return
            if not (_finite(d, net) and ci is not None and _finite(*ci)):
                eligible = False
                reasons.append("validation result not finite (NaN/inf): not eligible")
            else:
                reasons.append(f"validation: delta vs always-on {d:+.4f} (90% CI {ci[0]:+.4f}..{ci[1]:+.4f}), net return {net:+.4f} = delta vs cash")
                if d <= 0:
                    eligible = False
                    reasons.append("does not beat always-on on validation after costs")
                if net <= 0:
                    eligible = False
                    reasons.append("does not beat cash on validation (net return <= 0)")
                if ci[1] < 0:
                    reasons.append("validation CI is entirely below zero: worse than always-on")
                elif ci[0] <= 0:
                    reasons.append("validation CI includes zero; the frozen test decides")
                if _finite(regime_delta):
                    reasons.append(f"vs Lane A regime filter on validation: {d - regime_delta:+.4f} (reference, not a veto)")
                if _finite(half_delta):
                    reasons.append(f"vs constant half size on validation: {d - half_delta:+.4f} (exposure-only baseline; reference, not a veto)")
            if mix and max(mix.values()) >= DEGENERATE_SHARE:
                eligible = False
                reasons.append(f"degenerate: one multiplier on {max(mix.values()):.0%} of in-position validation decisions")
        fl = fold_line(spec)
        if fl:
            reasons.append(fl)
        if c is None or c.verdict != "approve_for_frozen_test":
            eligible = False
            reasons.append(f"critic veto: verdict '{c.verdict if c else 'missing'}'")
        if c and c.fragile_samples:
            eligible = False
            reasons += [f"critic (blocking): {x}" for x in c.fragile_samples]
        if c:
            reasons += [f"critic: {x}" for x in (c.overfit_risks + c.counterexamples)][:4]
        rows.append((p, spec, t, c, eligible, reasons))

    eligible_rows = [r for r in rows if r[4]]
    champion = max(eligible_rows, key=lambda r: r[2].delta_net_return_vs_always_on) if eligible_rows else None
    candidates = []

    def _vs_rule(t):
        return (t.delta_net_return_vs_always_on - rule_delta) if (t and _finite(rule_delta, t.delta_net_return_vs_always_on)) else None

    for p, spec, t, c, eligible, reasons in rows:
        is_champ = champion is not None and p is champion[0]
        if eligible and not is_champ:
            reasons = reasons + ["eligible but not selected: only the highest-validation-delta agent policy goes to the frozen test"]
        candidates.append(PolicyCandidate(
            policy_id=spec["policy_id"], spec_hash=spec_hash(spec), source="agent",
            role="agent_champion" if is_champ else "agent_not_selected",
            policy_spec=spec, status="accepted_for_frozen_test" if is_champ else "rejected",
            validation_delta_vs_always_on=t.delta_net_return_vs_always_on if t else None, validation_ci=t.ci_delta if t else None,
            validation_delta_vs_simple_rule=_vs_rule(t), validation_delta_vs_cash=t.net_return if t else None,
            allocation_mix=t.allocation_mix if t else {}, reasons=reasons,
            evidence_ids=[e for e in [*p.evidence_ids, t.evidence_id if t else None, *(c.evidence_ids if c else [])] if e],
        ))
    for source, spec in competitors:
        t = val_trial(spec)
        reasons = ["competitor: always carried to the frozen test for comparison"]
        if t and _finite(t.delta_net_return_vs_always_on, t.net_return):
            reasons.append(f"validation: delta vs always-on {t.delta_net_return_vs_always_on:+.4f}, net return {t.net_return:+.4f} = delta vs cash")
            if t.allocation_mix and max(t.allocation_mix.values()) >= DEGENERATE_SHARE:
                reasons.append(f"degenerate: one multiplier on {max(t.allocation_mix.values()):.0%} of in-position validation decisions")
        else:
            reasons.append("validation evaluation failed or not finite")
        fl = fold_line(spec)
        if fl:
            reasons.append(fl)
        if spec.get("summary"):
            reasons.append(f"Lane A: {spec['summary']}")
        candidates.append(PolicyCandidate(
            policy_id=spec["policy_id"], spec_hash=spec_hash(spec), source=source, role="competitor", policy_spec=spec,
            status="competitor", validation_delta_vs_always_on=t.delta_net_return_vs_always_on if t else None,
            validation_ci=t.ci_delta if t else None, validation_delta_vs_simple_rule=_vs_rule(t),
            validation_delta_vs_cash=t.net_return if t else None, allocation_mix=t.allocation_mix if t else {}, reasons=reasons,
            evidence_ids=[t.evidence_id] if t and t.evidence_id else [],
        ))

    # agent-layer verdict and the references Lane A's arbiter needs
    ao_net, ao_ci = always_on.get("net_return"), always_on.get("ci_net_return")
    basis = [f"always-on on validation: net {ao_net:+.4f}, 90% CI {ao_ci}" if _finite(ao_net) else "always-on validation metrics unavailable",
             "cash on validation: net 0.0000"]
    if half_t and _finite(half_delta, half_t.net_return):
        basis.append(f"constant half size on validation: delta vs always-on {half_delta:+.4f}, net {half_t.net_return:+.4f} "
                     "(a gate that mostly halves exposure should beat this)")
    if regime_note:
        basis.append(regime_note)
    if regime_t and _finite(regime_delta, regime_t.net_return):
        basis.append(f"Lane A regime filter on validation: delta vs always-on {regime_delta:+.4f}, net {regime_t.net_return:+.4f}")
    if ctx.health:
        basis.append(f"strategy health ({ctx.health['status']}): {ctx.health['summary']}")
    if champion:
        verdict = "candidate_for_frozen_test"
        basis.append(f"champion {champion[1]['policy_id']} beats always-on and cash on validation and passed the critic")
    else:
        verdict = "INCONCLUSIVE"
        basis.append("no agent gate met the pre-registered rule")
        if ao_ci and _finite(*ao_ci) and ao_ci[1] < 0:
            basis.append("note for Lane A's arbiter: the unchanged strategy's validation CI is below zero (it loses to cash)")

    # abandoned tool calls from timed-out stages
    still_running = ctx.wait_inflight(10.0)
    abandoned = sum(t.note.startswith("abandoned") for t in ctx.trials)
    if abandoned or still_running:
        limitations.append(f"{abandoned} agent tool call(s) finished after their stage timed out (logged as 'abandoned', not used); "
                           f"{still_running} still running when the report was written (not logged).")

    agent_specs = {t.spec_hash for t in ctx.trials if t.source == "agent" and t.spec_hash}
    all_specs = {t.spec_hash for t in ctx.trials if (t.status == "evaluated" or t.note.startswith("abandoned")) and t.spec_hash}
    limitations += [
        f"{len(agent_specs)} distinct agent gate specs attempted ({ctx.agent_tests_used()} agent train tests logged, refused ones included); "
        f"{len(all_specs)} distinct policies evaluated in total. Multiple-comparison risk applies to train and validation results.",
        "The critic can veto a proposal (part of the pre-registered rule); the critic sees validation results.",
        ("Bad luck vs broken: validation 14-day blocks of the unchanged strategy are compared with Lane A's train-only 14-day "
         "range, and exposure, turnover, costs, volatility and regime frequencies are compared train vs validation "
         "(pre-registered thresholds in health.py). Code computes it; only the critic sees it."
         if ctx.health else "Bad luck vs broken: not run (the loader gives no train predictive range or per-bar equity, or validation is shorter than one 14-day block)."),
        ("Walk-forward: every agent gate and competitor is also scored on Lane A's expanding train folds (same windows and "
         "2-bar embargo as the LightGBM walk-forward). Thresholds come from quantiles of the whole train window, so the folds "
         "are a stability check across train sub-periods, not unseen data, and they do not change the pre-registered selection."
         if any(fold_runs.values()) else
         f"Walk-forward: GateRunner.evaluate_folds failed ({ctx.fold_errors} error trial(s) in the trial log), so no fold stability check is reported."
         if ctx.fold_errors else
         "Walk-forward: the loader has no GateRunner.evaluate_folds, so no fold stability check was run."),
        "Regime effects are associations under lagged features, not causal.",
        "Returns convention: compounded simple returns after costs everywhere (Lane A contract); deltas and CIs use the same convention.",
        "The verdict only says whether an agent gate earned one sealed look; Lane A's arbiter makes the strategy decision.",
    ]
    if champion:
        limitations.append("Validation selected the single agent champion (max delta vs always-on among eligible); "
                           "this selection biases its validation number upwards; only the frozen test is unbiased.")
    if lgbm is not None:
        note = f"LightGBM competitor: single seed ({getattr(lgbm, 'seed', 'unknown')}); its result can vary with the seed."
        if (str(getattr(lgbm, "fitted_on", "")).startswith("train[")
                or str(getattr(lgbm, "calibrated_on", "")).startswith("train")):
            note += " Calibrated on late train instead of validation (spec deviation, keeps validation out-of-sample)."
        limitations.append(note)
    else:
        limitations.append(f"LightGBM competitor not run ({LGBM_UNAVAILABLE or 'not provided by loader'}).")
    if exp.coverage.get("news_sentiment", 0) < 0.9:
        limitations.append(f"news_sentiment coverage {exp.coverage.get('news_sentiment', 0):.0%}: not allowed in gates; market-only gating.")
    if news is None:
        limitations.append("No news source configured: no news context, no market-only vs market+news ablation.")

    if model is None:
        mode = "deterministic_fallback"
    elif all(used_llm):
        mode = "llm"
    else:
        mode = "llm_with_fallback"   # at least one stage fell back; agent_failures says which and why
    if mode != "llm":
        limitations.append(f"Agent mode '{mode}': some or all agent stages ran as deterministic fallback.")

    to_test = [c.policy_id for c in candidates if c.status in ("accepted_for_frozen_test", "competitor")]
    return InvestigationReport(
        experiment_id=exp.experiment_id, strategy_id=exp.strategy_id, generated_at=datetime.now(timezone.utc),
        agent_mode=mode, model_id=model_name(model), agent_failures=failures, verdict=verdict, verdict_basis=basis,
        champion_policy_id=champion[1]["policy_id"] if champion else None,
        validation_always_on={"net_return": ao_net, "ci_net_return": list(ao_ci) if ao_ci else None},
        diagnostic=diagnostic, proposals=proposals.proposals, critiques=critiques.critiques, trial_log=ctx.trials,
        candidates=candidates,
        test_requests=[f"Lane A: run ONCE on the sealed test split with identical costs: always_on, cash, {', '.join(to_test)}. "
                       "Report each vs always_on, vs cash and vs the simple rule, with CIs. Do not change any policy after seeing the result."],
        limitations=limitations, evidence=ctx.store.all(), n_distinct_agent_policies=len(agent_specs),
        n_policies_tried=len(all_specs), holdout_accessed=ctx.holdout_accessed,
        strategy_health=ctx.health, context=context,
    )
