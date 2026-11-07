from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil

import pytest
from fastapi import UploadFile
from fastapi import HTTPException
from pydantic import ValidationError

import apps.api.main as api
from apps.api.main import (
    ExperimentRequest,
    ImportRequest,
    PaperTestRequest,
    create_experiment,
    create_paper_test,
    demo_experiment,
    health,
    import_strategy,
    parse_timestamp,
    preview,
    strategies,
    validate_rows,
)


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch: pytest.MonkeyPatch):
    data_dir = Path(__file__).parents[2] / f".pytest_api_{uuid.uuid4().hex}"
    monkeypatch.setattr(api, "DATA_DIR", data_dir)
    monkeypatch.setattr(api, "UPLOAD_DIR", data_dir / "uploads")
    monkeypatch.setattr(api, "DB_PATH", data_dir / "keep_or_kill.sqlite3")
    api.init_db()
    api.seed_demo_data()
    yield
    shutil.rmtree(data_dir, ignore_errors=True)


def upload(filename: str, body: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(body), filename=filename)


def test_health_and_demo_seed_are_explicit() -> None:
    assert health()["research_engine"] is False
    listed = strategies()
    assert any(item["strategy_id"] == "demo_btc_trend_v1" and item["status"] == "demo" for item in listed)
    assert {item["strategy_id"] for item in listed} == {"demo_btc_trend_v1", "demo_btc_mean_reversion_v1"}
    for strategy in listed:
        runs = api.experiments(strategy_id=strategy["strategy_id"])
        assert runs and runs[0]["mode"] == "demo"
        assert len(runs[0]["equity"]) == 45
        assert len(runs[0]["regimes"]) == 6
        assert "illustrative" in runs[0]["message"].lower()


def test_positions_preview_suggests_industry_standard_mapping() -> None:
    body = b"timestamp,ticker,position\n2024-01-01T00:00:00Z,BTCUSDT,0.5\n"
    payload = preview(upload("positions.csv", body))
    assert payload["detected_kind"] == "positions"
    assert payload["suggested_mapping"] == {"decision_time": "timestamp", "symbol": "ticker", "target_position": "position"}
    assert payload["row_count"] == 1


def test_import_rejects_nan_duplicate_and_unknown_timezone() -> None:
    body = b"decision_time,symbol,target_position\n2024-01-01T00:00:00Z,BTCUSDT,nan\n2024-01-01T00:00:00Z,BTCUSDT,0.5\n"
    preview_result = preview(upload("positions.csv", body))
    request = ImportRequest(**{
        "upload_id": preview_result["upload_id"], "name": "Bad positions", "symbol": "BTCUSDT", "timeframe": "1h", "strategy_version": "v1",
        "kind": "positions", "mapping": preview_result["suggested_mapping"], "timezone": "Mars/Olympus", "fee_bps": 5, "slippage_bps": 2, "description": "",
    })
    request.upload_id = preview_result["upload_id"]
    request.mapping = preview_result["suggested_mapping"]
    payload = import_strategy(request)
    assert payload["valid"] is False
    codes = {item["code"] for item in payload["issues"]}
    assert "invalid_timezone" in codes or "invalid_row" in codes


def test_valid_trade_import_is_diagnosis_only_and_does_not_get_fixture_metrics() -> None:
    body = b"entry_time,exit_time,symbol,side,quantity,entry_price,exit_price\n2024-01-01T01:00:00Z,2024-01-01T04:00:00Z,BTCUSDT,long,1,42000,42500\n"
    preview_result = preview(upload("trades.csv", body))
    request = ImportRequest(**{
        "upload_id": preview_result["upload_id"], "name": f"Trade upload {uuid.uuid4().hex[:6]}", "symbol": "BTCUSDT", "timeframe": "1h", "strategy_version": "v1",
        "kind": "trades", "mapping": preview_result["suggested_mapping"], "timezone": "UTC", "fee_bps": 5, "slippage_bps": 2, "description": "source export",
    })
    request.mapping = preview_result["suggested_mapping"]
    imported = import_strategy(request)
    assert imported["valid"] is True
    strategy = imported["strategy"]
    assert strategy["status"] == "diagnosis_only"
    experiment = create_experiment(ExperimentRequest(strategy_id=strategy["strategy_id"]), None)
    assert experiment["status"] == "awaiting_engine"
    assert experiment["metrics"] == []
    assert experiment["verdict"] == "INCONCLUSIVE"


def test_paper_test_requires_approval_and_is_paper_only() -> None:
    experiment = demo_experiment("demo_btc_trend_v1", "fixture", "exp_test_paper")
    from apps.api.main import db_insert
    db_insert("experiments", experiment["experiment_id"], experiment)
    try:
        create_paper_test(PaperTestRequest(experiment_id=experiment["experiment_id"], duration_days=14, approved=False))
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("unapproved paper test should fail")
    plan = create_paper_test(PaperTestRequest(experiment_id=experiment["experiment_id"], duration_days=14, approved=True))
    assert plan["duration_days"] == 14
    assert plan["execution"] == "paper_only"
    assert "No trading" in plan["message"]


def test_timestamp_offset_is_normalized_and_dst_ambiguity_is_rejected() -> None:
    assert parse_timestamp("2024-01-01T01:00:00+01:00", "UTC").isoformat() == "2024-01-01T00:00:00+00:00"
    rows, issues, start, end = validate_rows(
        ["decision_time", "symbol", "target_position"],
        [{"decision_time": "2024-01-01T00:00:00Z", "symbol": "BTCUSDT", "target_position": "0.2"}],
        "positions", {"decision_time": "decision_time", "symbol": "symbol", "target_position": "target_position"}, "UTC",
    )
    assert rows and not [item for item in issues if item["severity"] == "error"] and start == end
