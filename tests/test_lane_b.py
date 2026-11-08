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
from packages.meta_policy import LGBM_UNAVAILABLE, LGBMGate, threshold_gate_allocation

needs_lgbm = pytest.mark.skipif(LGBMGate is None, reason=f"LightGBM unavailable: {LGBM_UNAVAILABLE}")
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


@needs_lgbm
def test_lgbm_trains_and_calibrates_on_train_only():
    _exp, _r, _tq, df, lgbm = _built()
    for split in ("test", "validation"):
        with pytest.raises(PermissionError):
            LGBMGate().fit(df.head(500), df["ret_next"].head(500), split=split)
    assert lgbm.fitted_on.startswith("train[")


@needs_lgbm
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
    expected = {"rule_baseline", "meta_model"} if LGBMGate is not None else {"rule_baseline"}
    assert {c.source for c in r.candidates if c.role == "competitor"} == expected
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
    assert r.agent_failures and r.agent_mode == "llm_with_fallback"
    assert r.verdict in ("candidate_for_frozen_test", "INCONCLUSIVE")


# ------------------------------------------------------------------ second adversarial review regressions

import math  # noqa: E402
import time as _time  # noqa: E402

from packages.research_agents.verify import unsupported_numbers, verify_critiques, verify_proposals  # noqa: E402
from packages.research_agents.tools import spec_hash  # noqa: E402


EV = [{"rows": [{"n_decisions": 2040, "n_trades": 128, "mean_net_return": -0.000203077441542493, "ci_low": -0.000456010541493941,
                 "ci_high": -1.05342030540653e-05, "hit_rate": 0.516003879728419, "total_cost": 0.2034}],
       "mix": {"0.0": 0.6875, "1.0": 0.3125}, "net": -0.4906}]


@pytest.mark.parametrize("text", ["made 9999 trades", "lost 87 bp per day", "Sharpe 4.2", "drawdown 0.07", "-0.4363", "3.5x",
                                  "forty percent", "15bp", "95% CI", "+0.4906"])
def test_verifier_flags_fabrications(text):
    assert unsupported_numbers(text, EV)


@pytest.mark.parametrize("text", ["mean -0.000203 over 128 trades (2040 decisions), 90% CI [-0.000456, -1.05e-05]",
                                  "hit rate 51.6%, off 68.75% of the time", "loses 49.06%", "net -0.4906", "2.03 bp",
                                  "on 2024-01-01T00:00:00 the q50 momentum_24h gate", "ev_arbiter_eval_1a557f5202"])
def test_verifier_accepts_copied_numbers(text):
    assert not unsupported_numbers(text, EV)


def test_verifier_random_numbers_rarely_match():
    rng = np.random.default_rng(0)
    hits = sum(not unsupported_numbers(f"{x:.3f}", EV) for x in rng.uniform(-1, 1, 500))
    assert hits / 500 < 0.05


def test_all_proposal_text_is_checked():
    ctx = make_ctx()
    ev = ctx.test_gate_train(gate(ctx, pid="agent::P1"))
    p = GateProposal(proposal_id="P1", based_on=["H1"], conditions=[ThresholdCondition(**gate(ctx)["conditions"][0])],
                     allocation_when_true=0.0, allocation_when_false=1.0, rationale="r", evidence_ids=[ev["evidence_id"]],
                     falsification_test="reject if the 95% CI of the validation delta includes zero")
    assert any("95%" in x for x in verify_proposals(ctx, ProposalSet(proposals=[p]), {"H1"}))


def test_cost_attribution_and_baselines_use_one_convention():
    ctx = make_ctx()
    costs = ctx.cost_attribution("train")
    ao = next(b for b in costs["baselines"] if b["policy"] == "always_on")
    assert costs["costs"][0]["net_return"] == pytest.approx(ao["metrics"]["net_return"], rel=1e-9)


class _Wrap:
    """Gate runner wrapper used to force edge cases."""
    def __init__(self, inner, edit):
        self.inner, self.edit = inner, edit

    def evaluate(self, spec, split):
        return self.edit(spec, self.inner.evaluate(spec, split))


def _loader_with(edit, quantile_keys_as_str=False):
    def loader(_):
        exp, runner, tq, _df, lgbm = _built()
        if quantile_keys_as_str:
            tq = {f: {str(q): v for q, v in qs.items()} for f, qs in tq.items()}
        return exp, _Wrap(runner, edit), tq, None, lgbm
    return loader


def _loader_forcing_vol_hypothesis(edit):
    """Force a clear train effect in vol_regime=high so the fallback proposes a gate (tests the arbiter, not the fixture)."""
    def loader(_):
        exp, runner, tq, _df, lgbm = _built()
        rows = [RegimeRow(**{**r.model_dump(), "ci_high": -abs(r.mean_net_return) / 4}) if (r.split == "train" and r.bucket == "high")
                else r for r in exp.per_regime]
        return exp.model_copy(update={"per_regime": rows}), _Wrap(runner, edit), tq, None, lgbm
    return loader


def test_champion_must_beat_cash():
    def edit(spec, ev):
        if spec.get("policy_id", "").startswith("agent::"):
            return ev.model_copy(update={"metrics": ev.metrics.model_copy(update={"net_return": -0.01})})
        return ev
    r = investigate("x", loader=_loader_forcing_vol_hypothesis(edit), force_fallback=True)
    assert any(c.source == "agent" for c in r.candidates)
    assert r.champion_policy_id is None
    assert any("does not beat cash" in reason for c in r.candidates if c.source == "agent" for reason in c.reasons)


def test_strategy_losing_to_cash_is_flagged_for_lane_a():
    def edit(spec, ev):
        ao = ev.always_on.model_copy(update={"net_return": -0.3, "ci_net_return": (-0.5, -0.1)})
        ev = ev.model_copy(update={"always_on": ao})
        if spec.get("policy_id", "").startswith("agent::"):
            ev = ev.model_copy(update={"delta_net_return_vs_always_on": -0.05})
        return ev
    r = investigate("x", loader=_loader_forcing_vol_hypothesis(edit), force_fallback=True)
    assert r.verdict == "INCONCLUSIVE" and r.champion_policy_id is None
    assert any("loses to cash" in b for b in r.verdict_basis)


def test_nan_validation_delta_is_never_champion():
    def edit(spec, ev):
        if spec.get("policy_id", "").startswith("agent::"):
            return ev.model_copy(update={"delta_net_return_vs_always_on": float("nan")})
        return ev
    r = investigate("x", loader=_loader_forcing_vol_hypothesis(edit), force_fallback=True)
    assert any(c.source == "agent" for c in r.candidates)
    assert r.champion_policy_id is None and r.model_dump_json()


def test_quantile_keys_from_json_strings_work():
    r = investigate("x", loader=_loader_with(lambda s, e: e, quantile_keys_as_str=True), force_fallback=True)
    assert r.candidates


def test_critic_approve_with_blocking_fragility_is_contradictory():
    from packages.research_agents.models import Critique, CritiqueSet
    ctx = make_ctx()
    spec = gate(ctx, pid="agent::P1")
    ev = ctx.arbiter_evaluate(spec, "validation")
    props = ProposalSet(proposals=[GateProposal(proposal_id="P1", based_on=["H1"], conditions=[ThresholdCondition(**spec["conditions"][0])],
                                                allocation_when_true=0.0, allocation_when_false=1.0, rationale="r",
                                                evidence_ids=[ev["evidence_id"]], falsification_test="f")])
    bad = CritiqueSet(critiques=[Critique(proposal_id="P1", verdict="approve_for_frozen_test", fragile_samples=["thin"],
                                          evidence_ids=[ev["evidence_id"]])])
    assert any("contradictory" in x for x in agents.verify_critiques(ctx, bad, props))


def test_agent_news_capped_at_train_end():
    ctx = make_ctx()
    val = next(w for w in ctx.experiment.windows if w.split == "validation")
    s, e = (val.start + timedelta(days=1)).isoformat(), (val.start + timedelta(days=2)).isoformat()
    with pytest.raises(ValueError):
        ctx.news_context(s, e, agent=True)
    assert "evidence_id" in ctx.news_context(s, e)          # the arbiter may read validation news


def test_equivalent_gates_share_a_hash_and_ci():
    ctx = make_ctx()
    q = ctx.train_quantiles["realized_vol_7d"][0.5]
    a = {"policy_id": "a", "family": "threshold_gate", "conditions": [{"feature": "realized_vol_7d", "op": "<=", "threshold": q}],
         "allocation_when_true": 1, "allocation_when_false": 0.0}
    b = {"policy_id": "b", "family": "threshold_gate", "conditions": [{"feature": "realized_vol_7d", "op": ">", "threshold": q}],
         "allocation_when_true": 0.0, "allocation_when_false": 1.0}
    assert spec_hash(a) == spec_hash(b)
    c1 = ctx.arbiter_evaluate({**a, "policy_id": "name1"}, "validation")["evaluation"]["ci_delta"]
    c2 = ctx.arbiter_evaluate({**a, "policy_id": "name2"}, "validation")["evaluation"]["ci_delta"]
    assert c1 == c2


def test_allocation_mix_counts_in_position_bars_only():
    ctx = make_ctx()
    g = gate(ctx, feature="momentum_24h", op="<=", q=0.5, a_t=0.0, a_f=1.0, pid="agent::mom")
    mix = ctx.arbiter_evaluate(g, "validation")["evaluation"]["allocation_mix"]
    assert max(mix.values()) >= 0.95          # the strategy is flat when momentum is low: this gate barely touches it


@needs_lgbm
def test_lgbm_spec_is_reproducible():
    spec = _built()[4].spec()
    assert spec["seed"] is not None and spec["model_sha256_16"]


def test_late_tool_calls_after_timeout_are_logged_as_abandoned(monkeypatch):
    monkeypatch.setattr(agents, "STAGE_TIMEOUT_S", 1.0)

    def edit(spec, ev):
        if spec.get("policy_id", "").startswith("agent::") and ev.split == "train":
            _time.sleep(2.0)
        return ev

    def fn(messages, info):
        parts = [p for msg in messages for p in getattr(msg, "parts", [])]
        if not any(isinstance(p, ToolReturnPart) for p in parts):
            return ModelResponse(parts=[ToolCallPart("regime_performance", {})])
        rets = [p for p in parts if isinstance(p, ToolReturnPart) and isinstance(p.content, dict) and "evidence_id" in p.content]
        if info.output_tools[0].name and any(t.name == "test_gate_train" for t in info.function_tools):
            q = _built()[2]["realized_vol_7d"][0.5]
            return ModelResponse(parts=[ToolCallPart("test_gate_train", {"conditions": [{"feature": "realized_vol_7d", "op": ">", "threshold": q}],
                                                                       "allocation_when_true": 0.0, "allocation_when_false": 1.0,
                                                                       "policy_id": "slow"})])
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, _hyp(rets[-1].content["evidence_id"]))])

    r = investigate("x", loader=_loader_with(edit), model=FunctionModel(fn))
    assert any(t.note.startswith("abandoned") for t in r.trial_log)
    assert any("abandoned" in lim for lim in r.limitations)


# ------------------------------------------------------------------ real-data Argon run (Lane A loader), round 3

def _proposal_with_text(ctx, rationale):
    ev = ctx.test_gate_train(gate(ctx, pid="agent::P1"))
    p = GateProposal(proposal_id="P1", based_on=["H1"], conditions=[ThresholdCondition(**gate(ctx)["conditions"][0])],
                     allocation_when_true=0.0, allocation_when_false=1.0, rationale=rationale, evidence_ids=[ev["evidence_id"]],
                     falsification_test="reject if the 90% CI of the validation delta includes zero")
    return verify_proposals(ctx, ProposalSet(proposals=[p]), {"H1"})


def test_numbers_the_agent_was_given_are_not_fabrications():
    ctx = make_ctx()      # fixture strategy id: btc-momentum-24h-demo
    assert not _proposal_with_text(ctx, "the 24h momentum strategy; buckets with fewer than 20 trades are weak")
    assert _proposal_with_text(ctx, "the 73h momentum strategy")


@pytest.mark.parametrize("text,ok", [("gross 0.3043", True), ("mean -3.54e-05", True), ("30.43%", True),
                                     ("gross 0.3044", False), ("mean -3.55e-05", False)])
def test_rounding_to_significant_digits_is_allowed_but_changing_digits_is_not(text, ok):
    ev = [{"gross_return": 0.304327785348499, "mean_net_return": -3.54385266639645e-05}]
    assert (not unsupported_numbers(text, ev)) is ok


def test_new_lane_a_features_are_allowlisted_only_where_covered():
    from packages.research_agents.allowlist import check_gate
    tq = {"atr_14": {0.5: 0.0042}}
    cond = [{"feature": "atr_14", "op": "<=", "threshold": 0.0042}]
    assert not check_gate(cond, 1.0, 0.5, {"atr_14": 1.0}, tq)
    assert check_gate(cond, 1.0, 0.5, {}, tq)          # loader without the feature -> refused


def test_default_timeouts_fit_a_strong_model():
    assert agents.REQUEST_TIMEOUT_S >= 180 and agents.STAGE_TIMEOUT_S >= 400


@pytest.mark.parametrize("text", ["over 73h", "a 5d window of 41 bars"])
def test_durations_glued_to_units_are_checked(text):
    assert unsupported_numbers(text, EV)


def test_small_durations_are_trivial_like_small_integers():
    assert not unsupported_numbers("a 7d window", EV) and unsupported_numbers("a 17d window", EV)


def test_lane_a_regime_filter_is_a_competitor_and_a_reference_for_agent_gates():
    exp, runner, tq, _df, lgbm = _built()

    class WithRegime:
        def __init__(self, inner):
            self._inner = inner
            self.regime_spec = {"policy_id": "rule::regime_filter", "family": "threshold_gate",
                                "conditions": [{"feature": "realized_vol_7d", "op": ">", "threshold": tq["realized_vol_7d"][0.67]}],
                                "allocation_when_true": 0.0, "allocation_when_false": 1.0, "summary": "flat in the top vol tercile"}

        def __getattr__(self, name):
            return getattr(self._inner, name)

    rep = investigate("x", model=None, loader=lambda _: (exp, WithRegime(runner), tq, None, lgbm))
    comp = next(c for c in rep.candidates if c.policy_id == "rule::regime_filter")
    assert comp.role == "competitor" and comp.status == "competitor"
    assert any("Lane A: flat in the top vol tercile" in r for r in comp.reasons)
    assert any("regime filter" in b for b in rep.verdict_basis)
    assert any(t.policy_id == "rule::regime_filter" and t.split == "validation" for t in rep.trial_log)


# ------------------------------------------------------------------ walk-forward folds (Lane A GateRunner.evaluate_folds)

class _WithFolds:
    """Stand-in runner plus evaluate_folds; fold deltas are scripted so stability can be tested."""

    def __init__(self, inner, deltas=(0.01, -0.02, -0.03)):
        self._inner, self.deltas, self.calls = inner, deltas, []

    def evaluate_folds(self, spec):
        self.calls.append(spec["policy_id"])
        base = self._inner.evaluate(spec, "train")
        return [base.model_copy(update={"fold": k, "delta_net_return_vs_always_on": d}) for k, d in enumerate(self.deltas, 1)]

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_folds_are_logged_as_train_evidence_and_reported_without_touching_the_holdout():
    from packages.research_agents.tools import is_fold
    exp, runner, tq, _df, lgbm = _built()
    wf = _WithFolds(runner)
    rep = investigate("x", model=None, loader=lambda _: (exp, wf, tq, None, lgbm))
    folds = [t for t in rep.trial_log if is_fold(t)]
    assert folds and all(t.split == "train" and t.source != "agent" and t.evidence_id for t in folds)
    assert "meta::lgbm_gate_v1" not in wf.calls          # fitted on all of train -> folds would be in-sample
    rule = next(c for c in rep.candidates if c.source == "rule_baseline")
    assert any("beats always-on on 1/3" in r for r in rule.reasons)
    assert any(l.startswith("Walk-forward: every agent gate") for l in rep.limitations)
    assert not rep.holdout_accessed


def test_fallback_critic_flags_gates_that_are_unstable_across_folds_and_ignores_folds_as_the_train_run():
    from packages.research_agents import fallback
    ctx = make_ctx()
    ctx.gate_runner = _WithFolds(ctx.gate_runner, deltas=(-0.01, -0.02, 0.03))
    spec = gate(ctx, pid="agent::P1")
    p = GateProposal(proposal_id="P1", based_on=["H1"], conditions=[ThresholdCondition(**spec["conditions"][0])],
                     allocation_when_true=0.0, allocation_when_false=1.0, rationale="r",
                     evidence_ids=[ctx.feature_grid()["evidence_id"]],
                     falsification_test="reject if the validation delta is not positive")
    ps = ProposalSet(proposals=[p])
    ctx.arbiter_folds(p.to_policy_spec())                  # folds first: must not be mistaken for the train run
    ctx.arbiter_evaluate(p.to_policy_spec(), "validation")
    c = fallback.critique(ctx, ps).critiques[0]
    assert any("1 of 3 walk-forward train folds" in r for r in c.overfit_risks)
    assert not [x for x in verify_critiques(ctx, fallback.critique(ctx, ps), ps) if "not copied" in x]


def test_runner_without_folds_is_disclosed():
    rep = investigate("x", model=None, loader=fixture_loader)
    assert any("no GateRunner.evaluate_folds" in l for l in rep.limitations)


# ------------------------------------------------------------------ bad luck vs broken (health.py)

def _health_exp(val_bar, shift=False, n_train=3360, n_val=1680):
    from types import SimpleNamespace as NS
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rng = np.random.default_rng(1)
    eq = [NS(split="train", decision_time=t0 + timedelta(hours=i), net_return=float(rng.normal(0, 0.003)), exposure=1.0)
          for i in range(n_train)]
    eq += [NS(split="validation", decision_time=t0 + timedelta(hours=n_train + i), net_return=val_bar(i, rng), exposure=1.0)
           for i in range(n_val)]
    m = lambda turn: NS(exposure=0.5, turnover=turn)  # noqa: E731
    regimes = [NS(regime_feature="sentiment_regime", split="train", bucket="fear", n_decisions=50),
               NS(regime_feature="sentiment_regime", split="train", bucket="greed", n_decisions=50),
               NS(regime_feature="sentiment_regime", split="validation", bucket="fear", n_decisions=99 if shift else 50),
               NS(regime_feature="sentiment_regime", split="validation", bucket="greed", n_decisions=1 if shift else 50)]
    return NS(train_predictive_range=NS(low=-0.09, high=0.10, horizon_bars=336), equity=eq,
              baselines=[NS(policy="always_on", split="train", metrics=m(60.0)), NS(policy="always_on", split="validation", metrics=m(30.0))],
              costs=[], per_regime=regimes)


def test_ordinary_losses_inside_the_training_range_are_not_called_a_breakdown():
    from packages.research_agents.health import strategy_health
    h = strategy_health(_health_exp(lambda i, r: 0.003 * (-1) ** i - 0.00002, shift=True))
    assert h["status"] == "within_training_range" and h["n_blocks"] == 5
    assert h["changed_assumptions"] == ["sentiment_regime_shares"] and "does not show the strategy broke" in h["summary"]


def test_many_blocks_below_the_range_are_flagged_as_outside():
    from packages.research_agents.health import strategy_health
    h = strategy_health(_health_exp(lambda i, r: -0.0005))
    assert h["status"] == "outside_training_range" and h["n_below"] == 5 and h["p_below"] < 0.05


def test_health_is_skipped_and_disclosed_without_a_train_range():
    from packages.research_agents.health import strategy_health
    assert strategy_health(build()[0]) is None
    rep = investigate("x", model=None, loader=fixture_loader)
    assert rep.strategy_health is None and any(l.startswith("Bad luck vs broken: not run") for l in rep.limitations)


def test_only_the_critic_can_read_strategy_health():
    tools = lambda a: set(a._function_toolset.tools)  # noqa: E731
    assert "strategy_health" in tools(agents._critic_agent("test", ProposalSet(proposals=[])))
    assert "strategy_health" not in tools(agents._diagnostic_agent("test")) | tools(agents._proposer_agent("test", set()))


def test_fallback_critic_says_when_the_gate_feature_regime_shifted():
    from packages.research_agents import fallback
    from packages.research_agents.health import strategy_health
    ctx = make_ctx()
    h = strategy_health(_health_exp(lambda i, r: float(r.normal(0, 0.003)), shift=True))
    ctx.health = {**h, "evidence_id": ctx.store.add("strategy_health", {}, h)}
    spec = gate(ctx, feature="fear_greed", op=">", q=0.5, a_t=1.0, a_f=0.0, pid="agent::P1")
    p = GateProposal(proposal_id="P1", based_on=["H1"], conditions=[ThresholdCondition(**spec["conditions"][0])],
                     allocation_when_true=1.0, allocation_when_false=0.0, rationale="r",
                     evidence_ids=[ctx.feature_grid()["evidence_id"]], falsification_test="reject if the validation delta is not positive")
    ps = ProposalSet(proposals=[p])
    ctx.arbiter_evaluate(p.to_policy_spec(), "validation")
    c = fallback.critique(ctx, ps).critiques[0]
    assert any("sentiment_regime_shares" in o for o in c.observations) and ctx.health["evidence_id"] in c.evidence_ids
    assert not verify_critiques(ctx, fallback.critique(ctx, ps), ps)


def test_redact_also_strips_test_equity_rows():
    from types import SimpleNamespace as NS
    from packages.research_agents.tools import redact
    exp = build()[0]
    leaky = exp.model_copy(update={"equity": [NS(split="validation"), NS(split="test")]})
    assert [r.split for r in redact(leaky).equity] == ["validation"]


# ------------------------------------------------------------------ adversarial review round 3 regressions

def test_degenerate_rule_applies_without_walk_forward_folds(monkeypatch):
    """R3-F1: rule (c) was nested under the fold line, so a runner without evaluate_folds skipped it."""
    from packages.research_agents import fallback
    from packages.research_agents.models import Critique, CritiqueSet

    def edit(spec, ev):
        if spec.get("policy_id", "").startswith("agent::") and ev.split == "validation":
            return ev.model_copy(update={"allocation_mix": {"0.0": 0.02, "0.5": 0.0, "1.0": 0.98},
                                         "delta_net_return_vs_always_on": 0.01, "ci_delta": (0.001, 0.02),
                                         "metrics": ev.metrics.model_copy(update={"net_return": 0.05})})
        return ev

    def approve(ctx, props):
        out = []
        for p in props.proposals:
            h = spec_hash(p.to_policy_spec())
            t = next(t for t in ctx.trials if t.spec_hash == h and t.split == "validation")
            out.append(Critique(proposal_id=p.proposal_id, verdict="approve_for_frozen_test", evidence_ids=[t.evidence_id]))
        return CritiqueSet(critiques=out)

    monkeypatch.setattr(fallback, "critique", approve)
    r = investigate("x", loader=_loader_forcing_vol_hypothesis(edit), force_fallback=True)
    agent = [c for c in r.candidates if c.source == "agent"]
    assert agent and r.champion_policy_id is None
    assert any("degenerate" in reason for reason in agent[0].reasons)


R3_EV = [{"hit_rate": 0.251, "n_trades": 151, "n_decisions": 5001, "delta": 0.0012, "mean": 0.9875}]


@pytest.mark.parametrize("text", ["mean .9876 per bar", "ci .5-.7", "delta −0.0012", "delta –0.0012",
                                  "hit rate 0.3", "2e2 trades", "1e4 decisions", "only 20 trades in high vol",
                                  "improvement 0.0%", "delta -0.0"])
def test_round3_verifier_leaks_are_closed(text):
    """R3-F4/F5/F7/F8/F9: leading dot, Unicode minus, loose rounding, e-notation integers, bare 20, zeros."""
    assert unsupported_numbers(text, R3_EV)


@pytest.mark.parametrize("text", ["hit rate 0.251 (25.1%)", "151 trades in 5001 decisions", "delta +0.0012, 0.12%",
                                  "buckets with fewer than 20 trades are weak", "sideways is fragile (<20 trades)",
                                  "mean 0.9875"])
def test_round3_verifier_still_accepts_honest_copies(text):
    assert not unsupported_numbers(text, R3_EV)


def test_uploaded_strategy_ids_do_not_hand_out_free_numbers():
    """R3-F6: digits inside an id/hash are not 'given' numbers; whole tokens of a demo id are."""
    from types import SimpleNamespace as NS
    from packages.research_agents.verify import context_numbers
    up = context_numbers(NS(experiment=NS(strategy_id="strat_3a2f1094c7e8", strategy_version="imported-positions")))
    demo = context_numbers(NS(experiment=NS(strategy_id="btc-trend-24-72-demo", strategy_version="v1")))
    assert up["strategy_label_numbers"] == [] and demo["strategy_label_numbers"] == [24.0, 72.0]


def test_empty_regime_filter_is_reported_as_always_on_not_a_competitor():
    """R3-F12: a filter that selected no buckets is always-on; it must not pose as a separate reference."""
    exp, runner, tq, _df, lgbm = _built()

    class EmptyRegime:
        regime_spec = {"policy_id": "rule::regime_filter", "family": "regime_gate", "flat_buckets": [], "full_buckets": [],
                       "allocation_flat": 0.0, "allocation_full": 1.0, "allocation_else": 1.0, "selected_on": "train",
                       "summary": "No train regime had an interval entirely off zero."}

        def __getattr__(self, name):
            return getattr(runner, name)

    rep = investigate("x", model=None, loader=lambda _: (exp, EmptyRegime(), tq, None, lgbm))
    assert not any(c.policy_id == "rule::regime_filter" for c in rep.candidates)
    assert any("equals always-on" in b for b in rep.verdict_basis)


def test_failed_folds_are_disclosed_as_failed_not_missing():
    """R3-F10."""
    exp, runner, tq, _df, lgbm = _built()

    class Raising:
        def evaluate_folds(self, spec):
            raise RuntimeError("boom")

        def __getattr__(self, name):
            return getattr(runner, name)

    rep = investigate("x", model=None, loader=lambda _: (exp, Raising(), tq, None, lgbm))
    assert any("evaluate_folds failed" in l for l in rep.limitations)
    assert any(t.status == "error" and "walk-forward folds failed" in t.note for t in rep.trial_log)


def test_fold_trials_carry_a_structured_fold_field():
    """R3-F11: folds are identified by TrialRecord.fold, not only by note text."""
    exp, runner, tq, _df, lgbm = _built()
    rep = investigate("x", model=None, loader=lambda _: (exp, _WithFolds(runner), tq, None, lgbm))
    folds = [t for t in rep.trial_log if t.fold is not None]
    assert folds and {t.fold for t in folds} == {1, 2, 3}
    assert all(t.fold is None for t in rep.trial_log if not t.note.startswith("walk-forward"))


def test_redact_drops_lane_a_notes_that_quote_the_sealed_verdict():
    """R3-F2: Lane A's dev view keeps a note with the test-derived verdict; agents never get it."""
    from packages.research_agents.tools import redact
    exp = build()[0]
    leaky = exp.model_copy(update={"notes": ["Verdict KEEP comes from the deterministic arbiter"]})
    assert redact(leaky).notes == []


def test_quantile_levels_from_the_feature_grid_are_citable():
    """Argon 8 Nov: 'fear_greed <= 43 (the 0.33 quantile)' was rejected because quantile levels are dict keys."""
    ctx = make_ctx()
    g = ctx.feature_grid()
    assert not unsupported_numbers("threshold at the 0.33 quantile (q=0.33) of realized_vol_7d", [g])
    assert unsupported_numbers("threshold at the 0.35 quantile", [g])
