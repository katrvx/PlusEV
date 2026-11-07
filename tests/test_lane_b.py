"""Lane B guardrail tests (AGENTS.md: no held-out labels, no strategy changes, claims link to
evidence ids, no unrestricted news backfill). Run: python3 -m pytest -q tests/test_lane_b.py"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from fixtures.lane_a_stub import build
from packages.meta_policy import LGBMGate
from packages.research_agents import agents
from packages.research_agents.investigate import investigate
from packages.research_agents.news import NewsRecord, NewsStore, content_hash
from packages.research_agents.tools import HoldoutAccessError, ToolContext


@lru_cache(maxsize=1)
def _built():
    return build()


def make_ctx(news=None) -> ToolContext:
    exp, runner, tq, _df, _lgbm = _built()
    return ToolContext(experiment=exp, gate_runner=runner, news=news, train_quantiles=tq)


# ------------------------------------------------------------------ holdout isolation

@pytest.mark.parametrize("call", [
    lambda c: c.regime_performance("test"),
    lambda c: c.cost_attribution("test"),
])
def test_tools_refuse_test_split(call):
    with pytest.raises(HoldoutAccessError):
        call(make_ctx())


def test_gate_test_on_holdout_is_refused_and_logged():
    ctx = make_ctx()
    spec = {"policy_id": "x", "family": "always_on"}
    with pytest.raises(HoldoutAccessError):
        ctx.test_gate_train(spec, split="test")
    assert ctx.holdout_accessed and ctx.trials[-1].status == "refused"


def test_news_window_cannot_reach_into_test():
    ctx = make_ctx()
    test_start = next(w.start for w in ctx.experiment.windows if w.split == "test")
    with pytest.raises(HoldoutAccessError):
        ctx.news_context((test_start - timedelta(days=2)).isoformat(), (test_start + timedelta(hours=1)).isoformat())


def test_lgbm_refuses_test_split():
    _exp, _r, _tq, df, _l = _built()
    with pytest.raises(PermissionError):
        LGBMGate().fit(df.head(100), df["ret_next"].head(100), split="test")


# ------------------------------------------------------------------ allowlist and budget

def test_gate_off_allowlist_is_refused_and_logged():
    ctx = make_ctx()
    bad = {"policy_id": "agent::bad", "family": "threshold_gate", "allocation_when_true": 0.3, "allocation_when_false": 1.0,
           "conditions": [{"feature": "future_return", "op": ">", "threshold": 0.0}]}
    out = ctx.test_gate_train(bad, split="train")
    assert "refused" in out and ctx.trials[-1].status == "refused"
    assert any("not allowlisted" in p for p in out["refused"]) and any("allocations" in p for p in out["refused"])


def test_threshold_must_be_on_training_grid():
    ctx = make_ctx()
    q50 = ctx.train_quantiles["realized_vol_7d"][0.5]
    ok = {"policy_id": "agent::ok", "family": "threshold_gate", "allocation_when_true": 0.0, "allocation_when_false": 1.0,
          "conditions": [{"feature": "realized_vol_7d", "op": ">", "threshold": q50}]}
    off = {**ok, "policy_id": "agent::off", "conditions": [{"feature": "realized_vol_7d", "op": ">", "threshold": q50 * 1.137}]}
    assert "evidence_id" in ctx.test_gate_train(ok)
    assert "refused" in ctx.test_gate_train(off)


def test_low_coverage_feature_refused():
    ctx = make_ctx()
    q = ctx.train_quantiles["news_sentiment"][0.5]
    spec = {"policy_id": "agent::news", "family": "threshold_gate", "allocation_when_true": 0.0, "allocation_when_false": 1.0,
            "conditions": [{"feature": "news_sentiment", "op": "<=", "threshold": q}]}
    out = ctx.test_gate_train(spec)
    assert any("coverage" in p for p in out["refused"])


def test_gate_test_budget():
    ctx = make_ctx()
    ctx.max_gate_tests = 2
    spec = {"policy_id": "p", "family": "always_on"}
    ctx.test_gate_train(spec)
    ctx.test_gate_train(spec)
    assert "refused" in ctx.test_gate_train(spec)


# ------------------------------------------------------------------ news point-in-time

def test_news_after_cutoff_is_invisible():
    t0 = datetime(2024, 1, 10, tzinfo=timezone.utc)
    recs = [NewsRecord(news_id=str(i), url=f"https://example.org/{i}", source="example", title=f"t{i}",
                       published_at=t0 + timedelta(hours=i), first_seen_at=t0 + timedelta(hours=i + 2),
                       content_hash=content_hash(f"t{i}")) for i in range(5)]
    store = NewsStore(recs)
    seen = store.visible(t0, t0 + timedelta(hours=10), cutoff=t0 + timedelta(hours=4))
    assert [r.news_id for r in seen] == ["0", "1", "2"]   # first_seen 2,3,4 <= cutoff 4; published time is irrelevant


# ------------------------------------------------------------------ agents cite only real evidence

def _scripted_diagnostic(cite_fake_first: bool):
    state = {"calls": 0}

    def fn(messages, info: AgentInfo) -> ModelResponse:
        state["calls"] += 1
        parts = [p for msg in messages for p in getattr(msg, "parts", [])]
        out_name = info.output_tools[0].name
        returns = [p for p in parts if isinstance(p, ToolReturnPart) and p.tool_name != out_name]
        # PydanticAI 2.x feeds an output-validator rejection back as a return on the output tool
        retried = any(getattr(p, "tool_name", None) == out_name and not isinstance(p, ToolCallPart) for p in parts)
        if not returns:
            return ModelResponse(parts=[ToolCallPart("regime_performance", {"split": "train"})])
        real_id = returns[0].content["evidence_id"]
        eid = "ev_made_up_123" if (cite_fake_first and not retried) else real_id
        report = {"summary": "s", "hypotheses": [{"hypothesis_id": "H1", "statement": "worse in high vol", "direction": "works_worse",
                                                  "conditions": ["vol_regime=high"], "evidence_ids": [eid], "confidence": "low",
                                                  "suggested_test": "gate on validation"}]}
        return ModelResponse(parts=[ToolCallPart(out_name, report)])

    return FunctionModel(fn), state


def test_agent_with_real_evidence_passes():
    model, _ = _scripted_diagnostic(cite_fake_first=False)
    ctx = make_ctx()
    out = agents.run_diagnostic(ctx, model)
    assert out.hypotheses[0].evidence_ids[0] in ctx.store


def test_agent_citing_fake_evidence_is_forced_to_retry():
    model, state = _scripted_diagnostic(cite_fake_first=True)
    ctx = make_ctx()
    out = agents.run_diagnostic(ctx, model)
    assert out.hypotheses[0].evidence_ids[0] in ctx.store
    assert state["calls"] >= 3            # tool call, rejected output, corrected output


def test_agent_tool_cannot_read_test_split():
    def fn(messages, info):
        returns = [p for msg in messages for p in getattr(msg, "parts", []) if isinstance(p, ToolReturnPart)]
        if not returns:
            return ModelResponse(parts=[ToolCallPart("regime_performance", {"split": "test"})])
        assert "error" in returns[0].content
        ok = [p for p in returns if "evidence_id" in p.content]
        if not ok:
            return ModelResponse(parts=[ToolCallPart("regime_performance", {"split": "train"})])
        report = {"summary": "s", "hypotheses": [{"hypothesis_id": "H1", "statement": "x", "direction": "works_worse", "conditions": [],
                                                  "evidence_ids": [ok[0].content["evidence_id"]], "confidence": "low", "suggested_test": "t"}]}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, report)])
    ctx = make_ctx()
    agents.run_diagnostic(ctx, FunctionModel(fn))
    assert ctx.holdout_accessed      # the attempt is recorded and disclosed in the report


# ------------------------------------------------------------------ end to end

def test_investigate_fallback_end_to_end():
    r = investigate("fixture", force_fallback=True)
    ids = {e.evidence_id for e in r.evidence}
    assert r.agent_mode == "deterministic_fallback" and not r.holdout_accessed
    assert all(set(h.evidence_ids) <= ids for h in r.diagnostic.hypotheses)
    assert all(set(c.evidence_ids) <= ids for c in r.candidates)
    assert r.n_policies_tried == sum(t.status != "refused" for t in r.trial_log)
    assert any(c.source == "meta_model" for c in r.candidates)
    assert all(t.split in ("train", "validation") for t in r.trial_log)
