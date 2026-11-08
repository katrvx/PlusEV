from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

import apps.api.main as api
from apps.api.judge_example import (
    DEFAULT_NATIVE_STRATEGY_ID,
    NATIVE_EXAMPLE_EXPERIMENT_ID,
    NATIVE_EXAMPLE_STRATEGY_ID,
    NATIVE_REPORTS,
    NATIVE_REPORT_STRATEGY_IDS,
)


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep API state inside pytest's managed temp tree, never repo root."""
    data_dir = tmp_path / "api-data"
    monkeypatch.setattr(api, "DATA_DIR", data_dir)
    monkeypatch.setattr(api, "UPLOAD_DIR", data_dir / "uploads")
    monkeypatch.setattr(api, "DB_PATH", data_dir / "keep_or_kill.sqlite3")
    api.init_db()
    api.seed_demo_data()
    yield


def test_default_real_bundle_preserves_identity_and_provenance() -> None:
    bundle = api.native_report_example()
    strategy = bundle["strategy"]
    experiment = bundle["experiment"]

    assert DEFAULT_NATIVE_STRATEGY_ID == "btc-meanrev-48-demo"
    assert strategy["strategy_id"] == DEFAULT_NATIVE_STRATEGY_ID
    assert strategy["source"] == "native_report"
    assert strategy["synthetic"] is False
    assert strategy["status"] == "ready"
    assert strategy["original_dataset_available"] is False
    assert strategy["dataset_hash"] == ""
    assert strategy["row_count"] == 0
    assert strategy["date_start"] == strategy["date_end"] == ""
    assert strategy["assumptions"]["fee_bps"] is None
    assert strategy["assumptions"]["slippage_bps"] is None

    assert experiment["experiment_id"] == NATIVE_EXAMPLE_EXPERIMENT_ID
    assert experiment["strategy_id"] == NATIVE_EXAMPLE_STRATEGY_ID
    assert experiment["source"] == "native_report"
    assert experiment["synthetic"] is False
    assert experiment["mode"] == "measured"
    assert experiment["verdict"] == "KILL"
    assert experiment["verdict_scope"] == "always_on"
    assert experiment["verdict_source_path"] == "docs/LANE_A_NOTE_FOR_C.md"
    assert experiment["paper_eligible"] is False
    assert experiment["holdout_accessed"] is False  # historical native report field
    assert experiment["metrics"] == []
    assert experiment["baselines"] == []
    assert experiment["equity"] == []
    assert experiment["regimes"] == []
    assert experiment["strategy_health"]["n_blocks"] == 45
    assert experiment["native_report"]["n_policies_tried"] == 9
    assert experiment["frozen_evaluation"]["experiment_id"] == NATIVE_EXAMPLE_EXPERIMENT_ID
    assert experiment["frozen_evaluation"]["evaluation"]["metrics"]["net_return"] < 0
    assert experiment["windows"]["test"] == "Sealed look attached; dates not supplied"
    assert experiment["policy"]["holdout_frozen"] is True
    assert experiment["policy"]["test_evaluated"] is True
    assert experiment["evidence"]
    assert experiment["evidence"][0]["args"] == bundle["investigation"]["report"]["evidence"][0]["args"]
    assert experiment["evidence"][0]["output"] == bundle["investigation"]["report"]["evidence"][0]["payload"]
    assert all(item["status"] == "inconclusive" for item in experiment["hypotheses"])
    assert api.db_get("strategies", "strategy_id", NATIVE_EXAMPLE_STRATEGY_ID) is None
    assert api.db_get("experiments", "experiment_id", NATIVE_EXAMPLE_EXPERIMENT_ID) is None


def test_trend_bundle_uses_n_policies_and_keeps_unseen_result_inconclusive() -> None:
    strategy_id = "btc-trend-24-72-demo"
    bundle = api.native_report_example(strategy_id)
    experiment = bundle["experiment"]

    assert experiment["experiment_id"] == NATIVE_REPORTS[strategy_id]["experiment_id"]
    assert experiment["verdict"] == "INCONCLUSIVE"
    assert experiment["verdict_scope"] == "candidate"
    assert experiment["native_report"]["n_policies_tried"] == 15
    assert experiment["strategy_health"]["n_blocks"] == 45
    assert experiment["strategy_health"]["n_above"] == 2
    assert "frozen_evaluation" not in experiment
    assert experiment["windows"]["test"] == "Not accessed"
    assert experiment["policy"]["holdout_frozen"] is False
    assert experiment["policy"]["test_evaluated"] is False
    assert experiment["holdout_accessed"] is False
    assert experiment["paper_eligible"] is False


def test_opt_in_collections_and_post_readback_are_consistent() -> None:
    assert not any(item["strategy_id"] in NATIVE_REPORT_STRATEGY_IDS for item in api.strategies())
    listed = api.strategies(include_native_example=True)
    assert {item["strategy_id"] for item in listed if item["strategy_id"] in NATIVE_REPORT_STRATEGY_IDS} == set(NATIVE_REPORT_STRATEGY_IDS)
    runs = api.experiments(strategy_id=DEFAULT_NATIVE_STRATEGY_ID)
    assert [item["experiment_id"] for item in runs] == [NATIVE_EXAMPLE_EXPERIMENT_ID]
    all_runs = api.experiments(include_native_example=True)
    assert {item["strategy_id"] for item in all_runs if item["strategy_id"] in NATIVE_REPORT_STRATEGY_IDS} == set(NATIVE_REPORT_STRATEGY_IDS)

    posted = api.create_experiment(api.ExperimentRequest(strategy_id=DEFAULT_NATIVE_STRATEGY_ID), None)
    assert posted["experiment_id"] == NATIVE_EXAMPLE_EXPERIMENT_ID
    assert posted["source"] == "native_report"
    assert api.db_get("experiments", "experiment_id", NATIVE_EXAMPLE_EXPERIMENT_ID) is None
    assert api.get_experiment(NATIVE_EXAMPLE_EXPERIMENT_ID) == posted


def test_report_download_is_read_only_and_paper_gate_stays_locked() -> None:
    response = api.report(NATIVE_EXAMPLE_EXPERIMENT_ID)
    payload = json.loads(response.body)
    assert payload["experiment_id"] == NATIVE_EXAMPLE_EXPERIMENT_ID
    assert payload["native_report"]["strategy_id"] == NATIVE_EXAMPLE_STRATEGY_ID
    assert payload["paper_eligible"] is False
    assert payload["equity"] == []
    with pytest.raises(HTTPException) as caught:
        api.create_paper_test(api.PaperTestRequest(experiment_id=NATIVE_EXAMPLE_EXPERIMENT_ID, duration_days=14, approved=True))
    assert caught.value.status_code == 409
    assert "no eligible paper proposal" in str(caught.value.detail)
    with pytest.raises(HTTPException) as unapproved:
        api.create_paper_test(api.PaperTestRequest(experiment_id=NATIVE_EXAMPLE_EXPERIMENT_ID, duration_days=14, approved=False))
    assert unapproved.value.status_code == 400
    assert api.db_get("experiments", "experiment_id", NATIVE_EXAMPLE_EXPERIMENT_ID) is None


def test_paper_gate_stays_locked_even_when_recorded_look_flags_are_true() -> None:
    recorded = api.native_report_example()["experiment"]
    assert recorded["paper_eligible"] is False
    assert recorded["policy"]["holdout_frozen"] is True
    assert recorded["policy"]["test_evaluated"] is True
    api.db_insert("experiments", recorded["experiment_id"], recorded)

    with pytest.raises(HTTPException) as caught:
        api.create_paper_test(api.PaperTestRequest(experiment_id=recorded["experiment_id"], duration_days=14, approved=True))
    assert caught.value.status_code == 409
    assert "no eligible paper proposal" in str(caught.value.detail)
    assert api.paper_tests() == []


def test_existing_id_wins_over_virtual_example() -> None:
    existing = {
        "experiment_id": NATIVE_EXAMPLE_EXPERIMENT_ID,
        "strategy_id": NATIVE_EXAMPLE_STRATEGY_ID,
        "status": "awaiting_engine",
        "mode": "pending",
        "created_at": "2026-11-08T00:00:00Z",
    }
    api.db_insert("experiments", NATIVE_EXAMPLE_EXPERIMENT_ID, existing)
    assert api.native_example_bundle() is None
    assert api.get_experiment(NATIVE_EXAMPLE_EXPERIMENT_ID) == existing


def test_legacy_projected_report_reads_through_without_mutating_saved_records() -> None:
    bundle = api.native_report_example()
    strategy = {**bundle["strategy"], "source": "recorded_investigation"}
    experiment = {**bundle["experiment"], "source": "recorded_investigation", "dataset_hash": "recorded-investigation"}
    api.db_insert("strategies", strategy["strategy_id"], strategy)
    api.db_insert("experiments", experiment["experiment_id"], experiment)

    restored = api.native_report_example()
    assert restored["strategy"]["source"] == "native_report"
    assert api.get_experiment(experiment["experiment_id"])["paper_eligible"] is False
    assert api.db_get("strategies", "strategy_id", strategy["strategy_id"]) == strategy
    assert api.db_get("experiments", "experiment_id", experiment["experiment_id"]) == experiment


@pytest.mark.parametrize("verdict", ["KILL", "INCONCLUSIVE"])
def test_measured_rejected_verdict_cannot_create_paper_plan(verdict: str) -> None:
    experiment = api.demo_experiment("demo_btc_trend_v1", "fixture", "exp_measured_rejected")
    experiment.update(mode="measured", verdict=verdict)
    api.db_insert("experiments", experiment["experiment_id"], experiment)
    with pytest.raises(HTTPException) as caught:
        api.create_paper_test(api.PaperTestRequest(experiment_id=experiment["experiment_id"], duration_days=14, approved=True))
    assert caught.value.status_code == 409
    assert api.paper_tests() == []
