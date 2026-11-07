"""Deterministic stand-ins for the three agents (spec: 'agent report may have deterministic
fixture fallback'). Same inputs, same tools, same output models, no LLM. Used when no model
is configured, in CI, and as a baseline the LLM agents must at least match.
"""

from __future__ import annotations

from .models import Critique, CritiqueSet, DiagnosticReport, GateProposal, Hypothesis, ProposalSet, ThresholdCondition
from .tools import ToolContext

MIN_TRADES = 20

# how a regime bucket maps onto an allowlisted feature condition (quantile keys of the training grid)
REGIME_TO_CONDITION = {
    ("vol_regime", "high"): ("realized_vol_7d", ">", 0.5),
    ("vol_regime", "low"): ("realized_vol_7d", "<=", 0.5),
    ("trend_regime", "bull"): ("momentum_24h", ">", 0.67),
    ("trend_regime", "bear"): ("momentum_24h", "<=", 0.33),
    ("trend_regime", "sideways"): ("momentum_24h", "<=", 0.67),
}


def diagnose(ctx: ToolContext) -> DiagnosticReport:
    perf = ctx.regime_performance("train")
    val = ctx.regime_performance("validation")
    costs = ctx.cost_attribution("train")
    val_rows = {(r["regime_feature"], r["bucket"]): r for r in val["rows"]}
    hyps, rejected = [], []
    for r in sorted(perf["rows"], key=lambda r: r["mean_net_return"]):
        key = (r["regime_feature"], r["bucket"])
        excludes_zero = r["ci_low"] > 0 or r["ci_high"] < 0
        if r["n_trades"] < MIN_TRADES:
            rejected.append(f"{key[0]}={key[1]}: only {r['n_trades']} trades on train; too few to say anything")
            continue
        if not excludes_zero:
            rejected.append(f"{key[0]}={key[1]}: train CI [{r['ci_low']:.2e}, {r['ci_high']:.2e}] spans zero")
            continue
        v = val_rows.get(key)
        same_sign = v is not None and (v["mean_net_return"] > 0) == (r["mean_net_return"] > 0)
        hyps.append(Hypothesis(
            hypothesis_id=f"H{len(hyps) + 1}",
            statement=f"The unchanged strategy performs {'worse' if r['mean_net_return'] < 0 else 'better'} when {key[0]} is {key[1]} "
                      f"(train mean {r['mean_net_return']:.2e} per interval after costs, n={r['n_decisions']}).",
            direction="works_worse" if r["mean_net_return"] < 0 else "works_better",
            conditions=[f"{key[0]}={key[1]}"],
            evidence_ids=[perf["evidence_id"], val["evidence_id"]],
            confidence="medium" if same_sign else "low",
            caveats=["validation sign agrees" if same_sign else "validation sign disagrees or bucket missing",
                     "regime label uses lagged features; descriptive, not yet a tested gate"],
            suggested_test=f"Gate on {key[0]}={key[1]} must improve validation net return vs always-on after switching costs.",
        ))
    if not hyps:
        hyps.append(Hypothesis(hypothesis_id="H1", statement="No regime bucket shows a train effect whose CI excludes zero.",
                               direction="works_worse", conditions=[], evidence_ids=[perf["evidence_id"]], confidence="low",
                               suggested_test="None; recommend INCONCLUSIVE unless more data."))
    c = costs["costs"][0] if costs["costs"] else {}
    summary = (f"Train net {c.get('net_return', 0):.3f} (gross {c.get('gross_return', 0):.3f}, switching costs {c.get('switching', 0):.3f}). "
               f"{len(hyps)} regime effect(s) with CI excluding zero on train; {len(rejected)} bucket(s) rejected as weak.")
    return DiagnosticReport(summary=summary, hypotheses=hyps[:6], rejected_explanations=rejected,
                            limitations=["deterministic fallback: no economic reasoning or news interpretation",
                                         "single strategy, single asset", "regime buckets are coarse (terciles / median)"])


def propose(ctx: ToolContext, diagnostic: DiagnosticReport) -> ProposalSet:
    grid = ctx.feature_grid()
    props = []
    for h in diagnostic.hypotheses:
        if not h.conditions:
            continue
        feat_bucket = tuple(h.conditions[0].split("="))
        mapped = REGIME_TO_CONDITION.get(feat_bucket)
        if not mapped:
            continue
        feature, op, q = mapped
        thr = ctx.train_quantiles[feature][q]
        bad = h.direction == "works_worse"
        spec = {"conditions": [ThresholdCondition(feature=feature, op=op, threshold=thr)],
                "allocation_when_true": 0.0 if bad else 1.0, "allocation_when_false": 1.0 if bad else 0.5}
        pid = f"P{len(props) + 1}"
        test = ctx.test_gate_train({"policy_id": f"agent::{pid}", "family": "threshold_gate",
                                    "conditions": [c.model_dump() for c in spec["conditions"]],
                                    "allocation_when_true": spec["allocation_when_true"],
                                    "allocation_when_false": spec["allocation_when_false"]}, split="train")
        props.append(GateProposal(
            proposal_id=pid, based_on=[h.hypothesis_id], conditions=spec["conditions"],
            allocation_when_true=spec["allocation_when_true"], allocation_when_false=spec["allocation_when_false"],
            rationale=f"Follows {h.hypothesis_id}: {'switch off' if bad else 'run at full size'} when {feature} {op} train q{int(q * 100)}.",
            evidence_ids=[e for e in (grid["evidence_id"], test.get("evidence_id"), *h.evidence_ids) if e],
            falsification_test="Reject if validation delta vs always-on is <= 0 after switching costs.",
        ))
    if not props:
        raise ValueError("no testable hypothesis; investigation should return INCONCLUSIVE")
    return ProposalSet(proposals=props[:4])


def critique(ctx: ToolContext, proposals: ProposalSet) -> CritiqueSet:
    out = []
    by_pid = {t.policy_id: t for t in ctx.trials if t.status == "evaluated"}
    for p in proposals.proposals:
        train = by_pid.get(f"agent::{p.proposal_id}")
        evs = [e for e in p.evidence_ids if e in ctx.store]
        risks, fragile = [], []
        if train is None:
            verdict = "reject"
            risks.append("no train evaluation found")
        else:
            payload = ctx.store.get(train.evidence_id).payload["evaluation"]
            exposure = payload["metrics"]["exposure"] / max(payload["always_on"]["exposure"], 1e-9)
            if exposure > 0.95 or exposure < 0.05:
                fragile.append(f"gate leaves exposure at {exposure:.0%} of always-on: barely a gate")
            n_tried = sum(t.status != "refused" for t in ctx.trials)
            if n_tried > 6:
                risks.append(f"{n_tried} policies tried so far; multiple-comparison risk")
            if train.ci_delta and train.ci_delta[0] <= 0:
                risks.append("train improvement CI includes zero")
            verdict = "approve_for_frozen_test" if (train.delta_net_return_vs_always_on or 0) > 0 and not fragile else "reject"
            evs.append(train.evidence_id)
        out.append(Critique(proposal_id=p.proposal_id, verdict=verdict, overfit_risks=risks, fragile_samples=fragile,
                            leakage_concerns=[] if all(c.feature != "news_sentiment" for c in p.conditions) else ["check news first-seen times"],
                            evidence_ids=evs or [ctx.feature_grid()["evidence_id"]]))
    return CritiqueSet(critiques=out)
