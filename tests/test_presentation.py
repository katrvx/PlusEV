"""Plain-language presentation layer (packages/research_agents/presentation.py).

It must add no numbers and no decisions, never let "checked" read as "passed", use the three stage names, say
"Not recorded" when something is missing, and keep the mean-reversion conclusion exact.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.research_agents.models import InvestigationReport
from packages.research_agents.presentation import NOT_RECORDED, present

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "experiments"
MEANREV = json.loads((EXP / "investigation_argon_meanrev.json").read_text())
TREND = json.loads((EXP / "investigation_argon_lane_a.json").read_text())
FIXTURE = json.loads((EXP / "investigation_fixture.json").read_text())
LOOK = json.loads((EXP / "frozen_look_btc-meanrev-48-demo.json").read_text())
KILL = {"verdict": "KILL", "source": "Lane A arbiter", "reason": "drawdown past the cap; net interval below zero."}
NOT_PROVEN = {"verdict": "INCONCLUSIVE", "source": "Lane A arbiter", "reason": "the held-out intervals still contain zero."}


def _all_text(p) -> str:
    return json.dumps(p.model_dump(mode="json"), ensure_ascii=False)


def test_meanrev_conclusion_is_exact_and_not_a_keep():
    p = present(MEANREV, held_out=LOOK, published=KILL)
    h = p.headline
    assert h.verdict == "KILL" and h.verdict_label == "Kill" and "original strategy" in h.verdict_scope
    assert "+27.3 pp" in h.meaning and "-28.9%" in h.meaning
    assert "not a new Keep verdict" in h.meaning
    assert "saved, not running" in h.next_action
    champ = next(f for f in p.filters if f.policy_id == MEANREV["champion_policy_id"])
    assert champ.outcome == "selected_for_further_testing" and "not approved" in champ.outcome_label
    assert champ.held_out and champ.held_out.own_return == pytest.approx(-0.28921116, abs=1e-6)
    assert champ.stages_checked[-1] == "Held-out test"
    assert p.filter_counts["approved"] == 0


@pytest.mark.parametrize("report,kw", [(MEANREV, {"held_out": LOOK, "published": KILL}), (TREND, {"published": NOT_PROVEN}),
                                       (FIXTURE, {}), (MEANREV, {})])
def test_checked_never_reads_as_passed(report, kw):
    p = present(report, **kw)
    for f in p.filters:
        assert f.outcome in {"rejected", "not_run", "selected_for_further_testing", "approved", "reference"}
        if f.outcome != "approved":
            assert "pass" not in f.outcome_label.lower() and "approved" not in f.outcome_label.replace("not approved", "")
    assert p.filter_counts["approved"] == 0          # nothing in these reports supports approval
    assert [s.stage for s in p.stages] == ["Training", "Validation", "Held-out test"]


def test_missing_held_out_says_not_recorded():
    p = present(MEANREV)                              # selected, but no look supplied
    assert p.stages[2].what_happened.startswith(NOT_RECORDED)
    assert "Nothing is approved yet" in p.headline.finding
    assert p.headline.verdict_label == NOT_RECORDED


def test_trend_is_not_proven_and_every_proposal_rejected():
    p = present(TREND, published=NOT_PROVEN)
    assert p.headline.verdict_label == "Not proven"
    proposed = [f for f in p.filters if f.proposed_by == "Proposer agent"]
    assert len(proposed) == 3 and all(f.outcome == "rejected" for f in proposed)
    assert p.takeaway.selected_filter is None
    critic = next(t for t in p.trace if t.actor == "Critic agent")
    assert critic.changed_conclusion and "best Validation number" in critic.changed_conclusion


def test_takeaway_is_honest_about_what_we_hold():
    p = present(MEANREV, held_out=LOOK, published=KILL)
    t = p.takeaway
    assert t.strategy.what_we_have == "positions_and_reference" and not t.strategy.runnable_code_included
    assert t.selected_filter["spec"]["conditions"][0]["feature"] == "realized_vol_7d"
    unknown = present({**FIXTURE, "strategy_id": "someone-elses-bot"})
    assert unknown.takeaway.strategy.what_we_have == "positions_only"
    supplied = present(FIXTURE, definition={"name": "x", "rule": "long when y", "parameters": {}, "source": "upload"})
    assert supplied.takeaway.strategy.what_we_have == "definition"


def test_every_evidence_id_exists_and_no_raw_ids_in_reasons():
    for report, kw in [(MEANREV, {"held_out": LOOK, "published": KILL}), (TREND, {"published": NOT_PROVEN})]:
        p = present(report, **kw)
        known = {e["evidence_id"] for e in report["evidence"]}
        for f in p.filters:
            assert set(f.evidence_ids) <= known
            assert "ev_" not in f.reason
        for s in p.trace:
            assert set(s.evidence_ids) <= known
        for s in p.stages:
            assert set(s.evidence_ids) <= known


def test_numbers_come_from_the_report():
    p = present(MEANREV, held_out=LOOK, published=KILL)
    for f in p.filters:
        c = next((c for c in MEANREV["candidates"] if c["policy_id"] == f.policy_id), None)
        if c:
            assert f.validation_vs_original_pp == c["validation_delta_vs_always_on"]
            assert f.validation_own_return == c["validation_delta_vs_cash"]


def test_report_model_accepts_presentation_and_old_reports_still_load():
    InvestigationReport.model_validate(MEANREV)                     # no presentation field: still valid
    r = InvestigationReport.model_validate({**MEANREV, "presentation": present(MEANREV).model_dump(mode="json")})
    assert r.presentation["headline"]["finding"]
