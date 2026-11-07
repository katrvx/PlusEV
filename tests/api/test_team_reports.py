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
