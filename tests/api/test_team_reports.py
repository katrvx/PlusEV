from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi import HTTPException

from apps.api import team_reports


FIXTURE = Path(__file__).resolve().parents[2] / "apps" / "api" / "fixtures" / "lane_b_investigation.json"


def configure(monkeypatch: pytest.MonkeyPatch, root: Path, fixture: Path) -> None:
    monkeypatch.setattr(team_reports, "ROOT", root)
    monkeypatch.setattr(team_reports, "FIXTURE_PATH", fixture)


def copy_fixture(root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURE, destination)


def test_bundled_fixture_is_explicit_and_preserves_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fixture = tmp_path / "apps" / "api" / "fixtures" / "lane_b_investigation.json"
    copy_fixture(tmp_path, fixture)
    configure(monkeypatch, tmp_path, fixture)
    items = team_reports.list_investigations()
    assert len(items) == 1
    assert items[0]["source"] == "bundled_lane_b_fixture"
    assert items[0]["synthetic"] is True
    assert items[0]["agent_mode"] == "deterministic_fallback"

    payload = team_reports.get_investigation(items[0]["experiment_id"])
    assert payload["report"]["evidence"][0]["evidence_id"].startswith("ev_")
    assert payload["report"]["holdout_accessed"] is False


def test_team_artifact_takes_precedence_over_bundled_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fixture = tmp_path / "apps" / "api" / "fixtures" / "lane_b_investigation.json"
    copy_fixture(tmp_path, fixture)
    artifact = tmp_path / "experiments" / "investigation_live.json"
    artifact.parent.mkdir(parents=True)
    report = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report["experiment_id"] = "exp_live_artifact"
    report["agent_mode"] = "llm"
    artifact.write_text(json.dumps(report), encoding="utf-8")

    configure(monkeypatch, tmp_path, fixture)
    items = team_reports.list_investigations()
    assert len(items) == 1
    assert items[0]["experiment_id"] == "exp_live_artifact"
    assert items[0]["source"] == "team_artifact"
    assert items[0]["synthetic"] is False


def test_invalid_team_artifact_is_not_silently_replaced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fixture = tmp_path / "apps" / "api" / "fixtures" / "lane_b_investigation.json"
    copy_fixture(tmp_path, fixture)
    artifact = tmp_path / "experiments" / "investigation_broken.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{ this is not json", encoding="utf-8")

    configure(monkeypatch, tmp_path, fixture)
    with pytest.raises(HTTPException) as caught:
        team_reports.list_investigations()
    assert caught.value.status_code == 500
    assert "Invalid investigation artifact" in str(caught.value.detail)


def test_invalid_lookup_id_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fixture = tmp_path / "apps" / "api" / "fixtures" / "lane_b_investigation.json"
    copy_fixture(tmp_path, fixture)
    configure(monkeypatch, tmp_path, fixture)
    with pytest.raises(HTTPException) as caught:
        team_reports.get_investigation("../secret")
    assert caught.value.status_code == 400
    assert caught.value.detail == "Invalid experiment_id"


def test_invalid_agent_mode_is_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fixture = tmp_path / "apps" / "api" / "fixtures" / "lane_b_investigation.json"
    copy_fixture(tmp_path, fixture)
    report = json.loads(fixture.read_text(encoding="utf-8"))
    report["agent_mode"] = "made_up_mode"
    fixture.write_text(json.dumps(report), encoding="utf-8")
    configure(monkeypatch, tmp_path, fixture)
    with pytest.raises(HTTPException) as caught:
        team_reports.list_investigations()
    assert caught.value.status_code == 500
    assert "agent_mode" in str(caught.value.detail)


def test_missing_holdout_flag_is_invalid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fixture = tmp_path / "apps" / "api" / "fixtures" / "lane_b_investigation.json"
    copy_fixture(tmp_path, fixture)
    report = json.loads(fixture.read_text(encoding="utf-8"))
    del report["holdout_accessed"]
    fixture.write_text(json.dumps(report), encoding="utf-8")
    configure(monkeypatch, tmp_path, fixture)
    with pytest.raises(HTTPException) as caught:
        team_reports.list_investigations()
    assert caught.value.status_code == 500
    assert "holdout_accessed" in str(caught.value.detail)


def test_unknown_nested_evidence_reference_is_invalid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fixture = tmp_path / "apps" / "api" / "fixtures" / "lane_b_investigation.json"
    copy_fixture(tmp_path, fixture)
    report = json.loads(fixture.read_text(encoding="utf-8"))
    report["diagnostic"]["hypotheses"][0]["evidence_ids"].append("ev_missing")
    fixture.write_text(json.dumps(report), encoding="utf-8")
    configure(monkeypatch, tmp_path, fixture)
    with pytest.raises(HTTPException) as caught:
        team_reports.list_investigations()
    assert caught.value.status_code == 500
    assert "ev_missing" in str(caught.value.detail)


def test_current_lane_b_fixture_is_preserved_and_labelled_sample_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    native = Path(__file__).resolve().parents[2] / "experiments" / "investigation_fixture.json"
    artifact = tmp_path / "experiments" / "investigation_fixture.json"
    artifact.parent.mkdir(parents=True)
    shutil.copyfile(native, artifact)
    configure(monkeypatch, tmp_path, tmp_path / "missing_bundled.json")

    original = json.loads(native.read_text(encoding="utf-8"))
    result = team_reports.get_investigation(original["experiment_id"])
    assert result["report"] == original
    assert result["source"] == "team_artifact"
    assert result["synthetic"] is True
    assert any(candidate["status"] == "competitor" for candidate in result["report"]["candidates"])


def test_mixed_model_run_keeps_its_failure_provenance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    artifact = tmp_path / "experiments" / "investigation_mixed.json"
    artifact.parent.mkdir(parents=True)
    report = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report.update(agent_mode="llm_with_fallback", model_id="example-model", agent_failures=["Critic unavailable; scripted check used."])
    artifact.write_text(json.dumps(report), encoding="utf-8")
    configure(monkeypatch, tmp_path, tmp_path / "missing_bundled.json")

    result = team_reports.get_investigation(report["experiment_id"])
    assert result["report"] == report
    assert team_reports.list_investigations()[0]["agent_mode"] == "llm_with_fallback"


def test_frozen_look_is_attached_only_to_its_own_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    experiments = tmp_path / "experiments"
    experiments.mkdir(parents=True)
    report = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report.update(experiment_id="exp_with_look", strategy_id="btc-look-demo")
    (experiments / "investigation_with_look.json").write_text(json.dumps(report), encoding="utf-8")
    other = dict(report, experiment_id="exp_other_run")
    (experiments / "investigation_other.json").write_text(json.dumps(other), encoding="utf-8")
    look = {
        "experiment_id": "exp_with_look",
        "strategy_id": "btc-look-demo",
        "champion_policy_id": "agent::gate",
        "evaluation": {
            "split": "test",
            "metrics": {"net_return": -0.2, "max_drawdown": 0.3},
            "always_on": {"net_return": -0.5, "max_drawdown": 0.6},
            "delta_net_return_vs_always_on": 0.3,
            "ci_delta": [0.1, 0.4],
        },
    }
    (experiments / "frozen_look_btc-look-demo.json").write_text(json.dumps(look), encoding="utf-8")
    configure(monkeypatch, tmp_path, tmp_path / "missing_bundled.json")

    matched = team_reports.get_investigation("exp_with_look")
    assert matched["frozen_look"] == look
    assert matched["report"] == report
    assert {"source", "synthetic", "source_path", "report"} <= set(matched)

    # Same strategy, different experiment: that look belongs to another run.
    assert "frozen_look" not in team_reports.get_investigation("exp_other_run")


def test_report_without_frozen_look_keeps_its_shape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fixture = tmp_path / "apps" / "api" / "fixtures" / "lane_b_investigation.json"
    copy_fixture(tmp_path, fixture)
    configure(monkeypatch, tmp_path, fixture)
    experiment_id = team_reports.list_investigations()[0]["experiment_id"]
    assert set(team_reports.get_investigation(experiment_id)) == {"source", "synthetic", "source_path", "report"}


def test_checked_in_meanrev_report_carries_its_frozen_look() -> None:
    result = team_reports.get_investigation("exp_a79497cf70ec")
    assert result["report"]["strategy_id"] == "btc-meanrev-48-demo"
    assert result["frozen_look"]["evaluation"]["split"] == "test"
    assert "frozen_look" not in team_reports.get_investigation("exp_dea9445d0576")
