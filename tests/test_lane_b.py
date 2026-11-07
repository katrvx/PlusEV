"""Lane B guardrail tests (AGENTS.md: no held-out labels, no strategy changes, claims link to
evidence ids, no unrestricted news backfill) plus regression tests for every finding of the
adversarial review. Run: python3 -m pytest -q tests/test_lane_b.py"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from fixtures.lane_a_stub import build
from packages.contracts_lane_b import RegimeRow
from packages.meta_policy import LGBMGate, threshold_gate_allocation
from packages.research_agents import agents
from packages.research_agents.investigate import investigate
from packages.research_agents.models import GateProposal, ProposalSet, ThresholdCondition
from packages.research_agents.news import NewsRecord, NewsStore, content_hash
from packages.research_agents.tools import HoldoutAccessError, ToolContext


@lru_cache(maxsize=1)
def _built():
    return build()


def make_ctx(news=None, exp=None) -> ToolContext:
    e, runner, tq, _df, _lgbm = _built()
    return ToolContext(experiment=exp or e, gate_runner=runner, news=news, train_quantiles=tq)


def gate(ctx, feature="realized_vol_7d", op=">", q=0.5, a_t=0.0, a_f=1.0, pid="agent::g"):
    return {"policy_id": pid, "family": "threshold_gate", "allocation_when_true": a_t, "allocation_when_false": a_f,
            "conditions": [{"feature": feature, "op": op, "threshold": ctx.train_quantiles[feature][q]}]}


def fixture_loader(_):
    exp, runner, tq, _df, lgbm = _built()
    return exp, runner, tq, None, lgbm


# ------------------------------------------------------------------ holdout isolation

@pytest.mark.parametrize("call", [lambda c: c.regime_performance("test"), lambda c: c.cost_attribution("TEST "),
                                  lambda c: c.arbiter_evaluate({"policy_id": "x", "family": "always_on"}, "test")])
def test_tools_refuse_test_split(call):
    with pytest.raises(HoldoutAccessError):
        call(make_ctx())


def test_split_typo_is_an_error_not_a_holdout_attempt():
    ctx = make_ctx()
    with pytest.raises(ValueError):
        ctx.regime_performance("Train")
    assert not ctx.holdout_accessed


def test_arbiter_holdout_attempt_is_logged_as_test():
    ctx = make_ctx()
    with pytest.raises(HoldoutAccessError):
        ctx.arbiter_evaluate({"policy_id": "x", "family": "always_on"}, "test")
    assert ctx.holdout_accessed and ctx.trials[-1].split == "test" and ctx.trials[-1].status == "refused"


def test_agent_memory_has_no_test_rows():
    ctx = make_ctx()
    assert all(r.split != "test" for r in ctx.experiment.per_regime)
    assert all(b.split != "test" for b in ctx.experiment.baselines) and all(c.split != "test" for c in ctx.experiment.costs)


def test_news_window_cannot_reach_into_test():
    ctx = make_ctx()
    test_start = next(w.start for w in ctx.experiment.windows if w.split == "test")
    with pytest.raises(HoldoutAccessError):
        ctx.news_context((test_start - timedelta(days=2)).isoformat(), (test_start + timedelta(hours=1)).isoformat())


def test_news_guard_fails_closed_without_windows():
    exp = _built()[0]
    ctx = make_ctx(exp=exp.model_copy(update={"windows": [w for w in exp.windows if w.split != "test"]}))
    with pytest.raises(HoldoutAccessError):
        ctx.news_context("2024-01-02", "2024-01-03")


def test_news_accepts_naive_and_date_only_times():
    ctx = make_ctx()
    out = ctx.news_context("2024-01-10", "2024-01-11T12:00:00")   # naive = UTC; no crash
    assert "evidence_id" in out


def test_lgbm_trains_and_calibrates_on_train_only():
    _exp, _r, _tq, df, lgbm = _built()
    for split in ("test", "validation"):
        with pytest.raises(PermissionError):
            LGBMGate().fit(df.head(500), df["ret_next"].head(500), split=split)
    assert lgbm.fitted_on.startswith("train[")


def test_lgbm_competitor_is_not_degenerate():
    _exp, _r, _tq, df, lgbm = _built()
    alloc = lgbm.allocation(df[df["split"] == "validation"])
    assert alloc.value_counts(normalize=True).max() < 0.95


# ------------------------------------------------------------------ allowlist, ops, budget

def test_gate_off_allowlist_is_refused_and_logged():
    ctx = make_ctx()
    bad = {"policy_id": "agent::bad", "family": "threshold_gate", "allocation_when_true": 0.3, "allocation_when_false": 1.0,
           "conditions": [{"feature": "future_return", "op": ">", "threshold": 0.0}]}
    out = ctx.test_gate_train(bad)
    assert "refused" in out and ctx.trials[-1].status == "refused"
    assert any("not allowlisted" in p for p in out["refused"]) and any("allocations" in p for p in out["refused"])


@pytest.mark.parametrize("op", ["<", ">=", "==", "LOL"])
def test_unknown_op_is_refused(op):
    ctx = make_ctx()
    out = ctx.test_gate_train(gate(ctx, op=op))
    assert "refused" in out and any("op" in p for p in out["refused"])


def test_gate_allocation_raises_on_unknown_op():
    with pytest.raises(ValueError):
        threshold_gate_allocation({"conditions": [{"feature": "x", "op": "<", "threshold": 0}], "allocation_when_true": 0,
                                   "allocation_when_false": 1}, pd.DataFrame({"x": [1.0]}))


@pytest.mark.parametrize("mutate", [lambda g: g["conditions"][0].pop("threshold"),
                                    lambda g: g["conditions"][0].update(threshold="high"),
                                    lambda g: g.update(allocation_when_true=False),
                                    lambda g: g["conditions"].append(dict(g["conditions"][0]))])
def test_malformed_gates_refused_without_crash(mutate):
    ctx = make_ctx()
    g = gate(ctx)
    mutate(g)
    assert "refused" in ctx.test_gate_train(g)


def test_threshold_must_be_on_training_grid():
    ctx = make_ctx()
    ok = gate(ctx)
    off = {**ok, "policy_id": "agent::off", "conditions": [{**ok["conditions"][0], "threshold": ok["conditions"][0]["threshold"] * 1.137}]}
    assert "evidence_id" in ctx.test_gate_train(ok)
    assert "refused" in ctx.test_gate_train(off)


def test_low_coverage_feature_refused():
    ctx = make_ctx()
    out = ctx.test_gate_train(gate(ctx, feature="news_sentiment", op="<="))
    assert any("coverage" in p for p in out["refused"])


def test_agent_budget_does_not_block_arbiter():
    ctx = make_ctx()
    ctx.max_agent_gate_tests = 2
    for i in range(3):
        ctx.test_gate_train(gate(ctx, pid=f"agent::{i}"))
    assert ctx.trials[-1].status == "refused" and "budget" in ctx.trials[-1].note
    out = ctx.arbiter_evaluate(gate(ctx, pid="agent::0"), "validation")
    assert "evidence_id" in out


def test_missing_data_is_conservative_both_directions():
    ctx_df = pd.DataFrame({"f": [np.nan, 2.0, 0.0]})
    off = {"conditions": [{"feature": "f", "op": ">", "threshold": 1.0}], "allocation_when_true": 0.0, "allocation_when_false": 1.0}
    on = {**off, "allocation_when_true": 1.0, "allocation_when_false": 0.5}
    assert threshold_gate_allocation(off, ctx_df).tolist() == [0.0, 0.0, 1.0]
    assert threshold_gate_allocation(on, ctx_df).tolist() == [0.5, 1.0, 0.5]


def test_evaluation_is_deterministic():
    ctx = make_ctx()
    a, b = ctx.arbiter_evaluate(gate(ctx), "validation"), ctx.arbiter_evaluate(gate(ctx), "validation")
    assert a["evaluation"]["ci_delta"] == b["evaluation"]["ci_delta"] and a["evidence_id"] == b["evidence_id"]


# ------------------------------------------------------------------ duplicate ids can't borrow results

def test_duplicate_proposal_ids_rejected():
    c = ThresholdCondition(feature="realized_vol_7d", op=">", threshold=0.01)
    p = dict(based_on=["H1"], conditions=[c], allocation_when_true=0.0, allocation_when_false=1.0, rationale="r",
             evidence_ids=["e"], falsification_test="f")
    with pytest.raises(ValidationError):
        ProposalSet(proposals=[GateProposal(proposal_id="P1", **p), GateProposal(proposal_id="P1", **p)])


def test_results_keyed_by_spec_not_name():
    ctx = make_ctx()
    good, bad = gate(ctx, op=">", pid="agent::P1"), gate(ctx, op="<=", pid="agent::P1")
    rg, rb = ctx.arbiter_evaluate(good, "validation"), ctx.arbiter_evaluate(bad, "validation")
    assert rg["spec_hash"] != rb["spec_hash"]
    assert rg["evaluation"]["delta_net_return_vs_always_on"] != rb["evaluation"]["delta_net_return_vs_always_on"]


# ------------------------------------------------------------------ news point-in-time

def test_news_after_cutoff_is_invisible_and_coverage_stays_in_window():
    t0 = datetime(2024, 1, 10, tzinfo=timezone.utc)
    recs = [NewsRecord(news_id=str(i), url=f"https://example.org/{i}", source="example", title=f"t{i}",
                       published_at=t0 + timedelta(hours=i), first_seen_at=t0 + timedelta(hours=i + 2),
                       content_hash=content_hash(f"t{i}")) for i in range(5)]
    store = NewsStore(recs + [recs[0].model_copy(update={"news_id": "late", "first_seen_at": t0 + timedelta(days=400)})])
    seen = store.visible(t0, t0 + timedelta(hours=10), cutoff=t0 + timedelta(hours=4))
    assert [r.news_id for r in seen] == ["0", "1", "2"]
    cov = store.coverage(t0, t0 + timedelta(hours=10))
    assert "late" not in str(cov) and cov["last_in_window"] < (t0 + timedelta(days=1)).isoformat()


# ------------------------------------------------------------------ agents cite only real evidence

def _script(build_output, first_call=("regime_performance", {"split": "train"}), cheat_first=False):
    state = {"calls": 0}

    def fn(messages, info: AgentInfo) -> ModelResponse:
        state["calls"] += 1
        parts = [p for msg in messages for p in getattr(msg, "parts", [])]
        out_name = info.output_tools[0].name
        returns = [p for p in parts if isinstance(p, ToolReturnPart) and p.tool_name != out_name]
        retried = any(getattr(p, "tool_name", None) == out_name and not isinstance(p, ToolCallPart) for p in parts)
        if not returns:
            return ModelResponse(parts=[ToolCallPart(*first_call)])
        return ModelResponse(parts=[ToolCallPart(out_name, build_output(returns, cheat_first and not retried))])

    return FunctionModel(fn), state


def _hyp(eid, statement="worse in high vol", conditions=("vol_regime=high",)):
    return {"summary": "s", "hypotheses": [{"hypothesis_id": "H1", "statement": statement, "direction": "works_worse",
                                            "conditions": list(conditions), "evidence_ids": [eid], "confidence": "low",
                                            "suggested_test": "gate on validation"}]}


def test_agent_with_real_evidence_passes():
    model, _ = _script(lambda r, cheat: _hyp(r[0].content["evidence_id"]))
    ctx = make_ctx()
    out = agents.run_diagnostic(ctx, model)
    assert out.hypotheses[0].evidence_ids[0] in ctx.store


def test_agent_citing_fake_evidence_is_forced_to_retry():
    model, state = _script(lambda r, cheat: _hyp("ev_made_up_123" if cheat else r[0].content["evidence_id"]), cheat_first=True)
    ctx = make_ctx()
    out = agents.run_diagnostic(ctx, model)
    assert out.hypotheses[0].evidence_ids[0] in ctx.store and state["calls"] >= 3


def test_fabricated_numbers_and_conditions_are_rejected():
    def build_out(r, cheat):
        eid = r[0].content["evidence_id"]
        if cheat:
            return _hyp(eid, statement="Train mean +9.99e-01 when moon_phase=full (n=99999)", conditions=["moon_phase=full"])
        row = next(x for x in r[0].content["rows"] if x["bucket"] == "high")
        return _hyp(eid, statement=f"train mean {row['mean_net_return']:.2e}, n={row['n_decisions']}")
    model, state = _script(build_out, cheat_first=True)
    out = agents.run_diagnostic(make_ctx(), model)
    assert "moon" not in out.hypotheses[0].statement and state["calls"] >= 3


def test_agent_cannot_read_validation_or_test():
    def build_out(r, cheat):
        assert "error" in r[0].content
        return _hyp("x")
    model, _ = _script(build_out, first_call=("regime_performance", {"split": "test"}))
    ctx = make_ctx()
    with pytest.raises(Exception):
        agents.run_diagnostic(ctx, model)       # can only cite a fake id -> retries exhausted
    assert ctx.holdout_accessed


def test_bad_tool_args_become_retries_not_crashes():
    def build_out(r, cheat):
        if any("error" in str(x.content) or "bad arguments" in str(x.content) for x in r):
            pass
        return _hyp(r[-1].content["evidence_id"]) if isinstance(r[-1].content, dict) and "evidence_id" in r[-1].content else _hyp("x")
    state = {"n": 0}

    def fn(messages, info):
        state["n"] += 1
        parts = [p for msg in messages for p in getattr(msg, "parts", [])]
        if state["n"] == 1:
            return ModelResponse(parts=[ToolCallPart("news_context", {"start": "not-a-date", "end": "2024-01-02"})])
        if state["n"] == 2:
            return ModelResponse(parts=[ToolCallPart("regime_performance", {})])
        rets = [p for p in parts if isinstance(p, ToolReturnPart) and isinstance(p.content, dict) and "evidence_id" in p.content]
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, _hyp(rets[-1].content["evidence_id"]))])
    out = agents.run_diagnostic(make_ctx(), FunctionModel(fn))
    assert out.hypotheses


def test_critic_must_review_real_proposals_with_their_evidence():
    ctx = make_ctx()
    spec = gate(ctx, pid="agent::P1")
    ev = ctx.arbiter_evaluate(spec, "validation")
    props = ProposalSet(proposals=[GateProposal(proposal_id="P1", based_on=["H1"], conditions=[ThresholdCondition(**spec["conditions"][0])],
                                                allocation_when_true=0.0, allocation_when_false=1.0, rationale="r",
                                                evidence_ids=[ev["evidence_id"]], falsification_test="f")])
    from packages.research_agents.models import Critique, CritiqueSet
    grid = ctx.feature_grid()["evidence_id"]
    ghost = CritiqueSet(critiques=[Critique(proposal_id="P_DOES_NOT_EXIST", verdict="approve_for_frozen_test", evidence_ids=[grid])])
    no_own = CritiqueSet(critiques=[Critique(proposal_id="P1", verdict="approve_for_frozen_test", evidence_ids=[grid])])
    good = CritiqueSet(critiques=[Critique(proposal_id="P1", verdict="approve_for_frozen_test", evidence_ids=[ev["evidence_id"]])])
    assert agents.verify_critiques(ctx, ghost, props)
    assert agents.verify_critiques(ctx, no_own, props)
    assert not agents.verify_critiques(ctx, good, props)


# ------------------------------------------------------------------ end to end

def test_investigate_fallback_end_to_end():
    r = investigate("fixture", loader=fixture_loader, force_fallback=True)
    ids = {e.evidence_id for e in r.evidence}
    assert r.agent_mode == "deterministic_fallback" and not r.holdout_accessed
    assert all(set(h.evidence_ids) <= ids for h in r.diagnostic.hypotheses)
    assert all(set(c.evidence_ids) <= ids for c in r.candidates)
    assert sum(c.status == "accepted_for_frozen_test" for c in r.candidates) <= 1            # at most ONE agent champion
    assert {c.source for c in r.candidates if c.role == "competitor"} == {"rule_baseline", "meta_model"}
    assert all(c.validation_delta_vs_simple_rule is not None for c in r.candidates if c.validation_delta_vs_always_on is not None)
    assert not any(t.split == "test" for t in r.trial_log)
    assert r.model_dump_json()


def test_inconclusive_when_no_effect():
    exp, runner, tq, _df, lgbm = _built()
    flat = [RegimeRow(**{**row.model_dump(), "ci_low": -1.0, "ci_high": 1.0}) for row in exp.per_regime]
    loader = lambda _: (exp.model_copy(update={"per_regime": flat}), runner, tq, None, lgbm)  # noqa: E731
    r = investigate("x", loader=loader, force_fallback=True)
    assert r.verdict == "INCONCLUSIVE" and r.champion_policy_id is None and not r.proposals
    assert any(c.role == "competitor" for c in r.candidates)


def test_llm_failure_falls_back_and_is_disclosed():
    def broken(messages, info):
        return ModelResponse(parts=[ToolCallPart("regime_performance", {"split": 42})])
    r = investigate("fixture", loader=fixture_loader, model=FunctionModel(broken))
    assert r.agent_failures and r.agent_mode in ("deterministic_fallback", "llm_with_fallback")
    assert r.verdict in ("candidate_for_frozen_test", "INCONCLUSIVE")
