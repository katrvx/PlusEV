"""Lane B's investigate() against Lane A's loader, not the synthetic stand-in."""

from __future__ import annotations

import pytest

from kok_a.experiment import load_for_lane_b, score_frozen
from kok_a.market import SNAPSHOT_SYNTHETIC
from packages.research_agents.investigate import investigate


def test_loader_hides_the_sealed_test_from_agents():
    result, runner, quantiles, news, lgbm = load_for_lane_b(SNAPSHOT_SYNTHETIC)
    assert news is None and lgbm.fitted_on == "train"
    assert any(window.split == "test" for window in result.windows)
    assert result.decision is None and result.paper_plan is None
    assert all(row.split != "test" for row in result.baselines)
    assert "momentum_24h" in quantiles and 0.5 in quantiles["realized_vol_7d"]
    with pytest.raises(PermissionError):
        runner.evaluate({"policy_id": "cash", "family": "cash"}, "test")


def test_fallback_investigation_uses_lane_a_and_leaves_the_holdout_sealed():
    loaded = load_for_lane_b(SNAPSHOT_SYNTHETIC)
    report = investigate(SNAPSHOT_SYNTHETIC, loader=lambda _experiment_id: loaded, force_fallback=True)
    assert report.holdout_accessed is False
    assert report.agent_mode == "deterministic_fallback"
    assert all(trial.split in ("train", "validation") for trial in report.trial_log)
    assert any(candidate.source == "rule_baseline" and candidate.status == "competitor" for candidate in report.candidates)
    assert any(candidate.source == "meta_model" for candidate in report.candidates)
    ids = {item.evidence_id for item in report.evidence}
    assert all(set(hypothesis.evidence_ids) <= ids for hypothesis in report.diagnostic.hypotheses)
    assert report.holdout_accessed is False

    rule = next(candidate.policy_spec for candidate in report.candidates if candidate.source == "rule_baseline")
    first = score_frozen(loaded[1], [rule])[0]
    assert first.split == "test"
    again = score_frozen(loaded[1], [rule])[0]
    assert again.metrics.net_return == pytest.approx(first.metrics.net_return)
    changed = dict(rule)
    changed["family"] = "cash"
    with pytest.raises(PermissionError):
        score_frozen(loaded[1], [changed])


def test_unknown_experiment_id_is_rejected():
    with pytest.raises(KeyError):
        load_for_lane_b("fixture")
