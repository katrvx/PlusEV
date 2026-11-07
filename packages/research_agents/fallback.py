"""Deterministic stand-ins for the three agents (spec: 'agent report may have deterministic
fixture fallback'). Same inputs, same tools, same output models, same verification, no LLM.
Used when no model is configured, when an LLM stage fails, in CI, and as a baseline the LLM
agents must at least match. Like the agents, it reads TRAIN data only.
"""

from __future__ import annotations

from .models import Critique, CritiqueSet, DiagnosticReport, GateProposal, Hypothesis, ProposalSet, ThresholdCondition
from .health import feature_shift
from .tools import ToolContext, is_fold, spec_hash

MIN_TRADES = 20
DEGENERATE_SHARE = 0.95   # a gate that keeps one multiplier on >= 95% of decisions is barely a gate

# regime bucket -> allowlisted feature conditions (quantile keys of the training grid)
REGIME_TO_CONDITIONS = {
    ("vol_regime", "high"): [("realized_vol_7d", ">", 0.5)],
    ("vol_regime", "low"): [("realized_vol_7d", "<=", 0.5)],
    ("trend_regime", "bull"): [("momentum_24h", ">", 0.67)],
    ("trend_regime", "bear"): [("momentum_24h", "<=", 0.33)],
    ("trend_regime", "sideways"): [("momentum_24h", ">", 0.33), ("momentum_24h", "<=", 0.67)],
}


def diagnose(ctx: ToolContext) -> DiagnosticReport:
    perf = ctx.regime_performance("train")
    costs = ctx.cost_attribution("train")
    hyps, rejected = [], []
    for r in sorted(perf["rows"], key=lambda r: r["mean_net_return"]):
        key = f"{r['regime_feature']}={r['bucket']}"
        excludes_zero = r["ci_low"] > 0 or r["ci_high"] < 0
        if r["n_trades"] < MIN_TRADES:
            rejected.append(f"{key}: only {r['n_trades']} trade entries on train; too few to say anything")
            continue
        if not excludes_zero:
            rejected.append(f"{key}: train CI spans zero")
            continue
        width = r["ci_high"] - r["ci_low"]
        hyps.append(Hypothesis(
            hypothesis_id=f"H{len(hyps) + 1}",
            statement=f"The unchanged strategy performs {'worse' if r['mean_net_return'] < 0 else 'better'} when {key} "
                      f"(train mean {r['mean_net_return']:.2e} per interval after costs, n={r['n_decisions']}).",
            direction="works_worse" if r["mean_net_return"] < 0 else "works_better",
            conditions=[key],
            evidence_ids=[perf["evidence_id"]],
            confidence="medium" if abs(r["mean_net_return"]) > width / 2 else "low",
            caveats=["train only; validation is reserved for the arbiter",
                     "regime label uses lagged features; descriptive, not yet a tested gate"],
            suggested_test=f"A gate on {key} must improve validation net return vs always-on and vs the simple rule after costs.",
        ))
    if not hyps:
        hyps.append(Hypothesis(hypothesis_id="H0", statement="No regime bucket shows a train effect whose CI excludes zero.",
                               direction="works_worse", conditions=[], evidence_ids=[perf["evidence_id"]], confidence="low",
                               suggested_test="None; the honest outcome is INCONCLUSIVE unless more data arrives."))
    c = costs["costs"][0] if costs["costs"] else {}
    summary = (f"Train net {c.get('net_return', 0):.3f} (gross {c.get('gross_return', 0):.3f}). "
               f"{sum(bool(h.conditions) for h in hyps)} regime effect(s) with CI excluding zero on train; "
               f"{len(rejected)} bucket(s) rejected as weak.")
    return DiagnosticReport(summary=summary, hypotheses=hyps[:6], rejected_explanations=rejected,
                            limitations=["deterministic fallback: no economic reasoning or news interpretation",
                                         "single strategy, single asset", "regime buckets are coarse (terciles / median)"])


def propose(ctx: ToolContext, diagnostic: DiagnosticReport) -> ProposalSet:
    grid = ctx.feature_grid()
    props = []
    for h in diagnostic.hypotheses:
        if not h.conditions:
            continue
        feat, bucket = h.conditions[0].split("=", 1)
        mapped = REGIME_TO_CONDITIONS.get((feat, bucket))
        if not mapped:
            continue
        conds = [ThresholdCondition(feature=f, op=op, threshold=ctx.train_quantiles[f][q]) for f, op, q in mapped]
        bad = h.direction == "works_worse"
        a_t, a_f = (0.0, 1.0) if bad else (1.0, 0.5)
        pid = f"P{len(props) + 1}"
        test = ctx.test_gate_train({"policy_id": f"agent::{pid}", "family": "threshold_gate",
                                    "conditions": [c.model_dump() for c in conds],
                                    "allocation_when_true": a_t, "allocation_when_false": a_f})
        props.append(GateProposal(
            proposal_id=pid, based_on=[h.hypothesis_id], conditions=conds, allocation_when_true=a_t, allocation_when_false=a_f,
            rationale=f"Follows {h.hypothesis_id}: {'switch off' if bad else 'run at full size'} when {h.conditions[0]} holds.",
            evidence_ids=[e for e in (grid["evidence_id"], test.get("evidence_id"), *h.evidence_ids) if e],
            falsification_test="Reject if validation delta vs always-on is <= 0 after switching costs.",
        ))
    return ProposalSet(proposals=props[:4])


def critique(ctx: ToolContext, proposals: ProposalSet) -> CritiqueSet:
    out = []
    for p in proposals.proposals:
        h = spec_hash(p.to_policy_spec())
        train = next((t for t in ctx.trials if t.spec_hash == h and t.split == "train" and t.status == "evaluated"
                      and not is_fold(t)), None)
        folds = [t for t in ctx.trials if t.spec_hash == h and is_fold(t) and t.status == "evaluated"
                 and t.delta_net_return_vs_always_on is not None]
        val = next((t for t in ctx.trials if t.spec_hash == h and t.split == "validation" and t.status == "evaluated"), None)
        risks, fragile, counter, evs = [], [], [], []
        for t in (train, val):
            if t and t.evidence_id:
                evs.append(t.evidence_id)
        if val is None:
            verdict = "reject"
            risks.append("no validation evaluation by the arbiter")
        else:
            top = max(val.allocation_mix.values()) if val.allocation_mix else 1.0
            if top >= DEGENERATE_SHARE:
                fragile.append(f"one multiplier on {top:.0%} of validation decisions: barely a gate")
            if train and train.delta_net_return_vs_always_on and val.delta_net_return_vs_always_on is not None \
                    and (train.delta_net_return_vs_always_on > 0) != (val.delta_net_return_vs_always_on > 0):
                counter.append("train and validation disagree in sign")
            obs = []
            if val.ci_delta and val.ci_delta[0] <= 0:
                obs.append("validation improvement CI includes zero")
            if folds:
                wins = sum(t.delta_net_return_vs_always_on > 0 for t in folds)
                if 2 * wins < len(folds):
                    risks.append(f"beats always-on on only {wins} of {len(folds)} walk-forward train folds: unstable over time")
                evs.append(folds[-1].evidence_id)
            shifted = feature_shift(ctx.health, [c.feature for c in p.conditions])
            if shifted:
                obs.append(f"the regime behind this gate's feature shifted between train and validation ({', '.join(shifted)}): "
                           "the validation result may reflect that shift, not a stable effect")
                evs.append(ctx.health["evidence_id"])
            if ctx.agent_tests_used() > 6:
                risks.append("many agent train tests (see trial log): multiple-comparison risk")
            verdict = "approve_for_frozen_test" if (val.delta_net_return_vs_always_on or 0) > 0 and not fragile and not counter else "reject"
        out.append(Critique(proposal_id=p.proposal_id, verdict=verdict, overfit_risks=risks, fragile_samples=fragile,
                            counterexamples=counter, observations=obs if val is not None else [],
                            leakage_concerns=[] if all(c.feature != "news_sentiment" for c in p.conditions) else ["check news first-seen times"],
                            evidence_ids=evs or [ctx.feature_grid()["evidence_id"]]))
    return CritiqueSet(critiques=out)
