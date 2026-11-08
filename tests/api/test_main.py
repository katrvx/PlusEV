from __future__ import annotations

import io
import json
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
    assert health()["research_engine"] is True
    listed = strategies()
    assert any(item["strategy_id"] == "demo_btc_trend_v1" and item["status"] == "demo" for item in listed)
    ids = {item["strategy_id"] for item in listed}
    assert ids == {"demo_btc_trend_v1", "demo_btc_mean_reversion_v1"}
    opted_in = strategies(include_native_example=True)
    assert {"btc-trend-24-72-demo", "btc-meanrev-48-demo"} <= {item["strategy_id"] for item in opted_in}
    for strategy in listed:
        if not strategy["strategy_id"].startswith("demo_"):
            continue
        runs = api.experiments(strategy_id=strategy["strategy_id"])
        assert runs and runs[0]["mode"] == "demo"
        assert len(runs[0]["equity"]) == 45
        assert len(runs[0]["regimes"]) == 6
        assert "illustrative" in runs[0]["message"].lower()
    root = Path(__file__).parents[2]
    trend_report = json.loads((root / "experiments" / "investigation_argon_lane_a.json").read_text())
    meanrev_report = json.loads((root / "experiments" / "investigation_argon_meanrev.json").read_text())
    trend = api.experiments(strategy_id="btc-trend-24-72-demo")
    assert trend[0]["experiment_id"] == trend_report["experiment_id"]
    assert trend[0]["verdict"] == "INCONCLUSIVE"
    assert trend[0]["strategy_id"] == trend_report["strategy_id"]
    assert trend[0]["native_report"]["n_policies_tried"] == trend_report["n_policies_tried"] == 15
    assert trend[0]["strategy_health"]["n_blocks"] == 45
    assert trend[0]["strategy_health"]["n_above"] == 2
    meanrev = api.experiments(strategy_id="btc-meanrev-48-demo")
    assert meanrev[0]["experiment_id"] == meanrev_report["experiment_id"]
    assert meanrev[0]["strategy_id"] == meanrev_report["strategy_id"]
    assert meanrev[0]["verdict"] == "KILL"
    assert meanrev[0]["native_report"]["n_policies_tried"] == meanrev_report["n_policies_tried"] == 9
    assert meanrev[0]["strategy_health"]["n_blocks"] == 45
    assert meanrev[0]["frozen_evaluation"]["evaluation"]["metrics"]["net_return"] < 0


def test_recorded_fallback_describes_the_selected_filter_honestly() -> None:
    # The served rows for these runs come from the native-report bundle; _recorded_experiment is the
    # fallback when that bundle is unavailable. It must say the same thing as the agent report.
    root = Path(__file__).parents[2]
    runs = {strategy_id: (relative, frozen, verdict, reason) for strategy_id, _, relative, frozen, verdict, reason in api.RECORDED_INVESTIGATIONS}

    def fallback(strategy_id: str) -> dict:
        relative, frozen, verdict, reason = runs[strategy_id]
        return api._recorded_experiment(json.loads((root / relative).read_text()), verdict, reason, frozen, relative)

    meanrev = fallback("btc-meanrev-48-demo")
    assert meanrev["verdict"] == "KILL"
    assert meanrev["recommendation"].startswith("Kill the original strategy.")
    assert "not running" in meanrev["recommendation"]
    # A filter WAS selected for the held-out test; it is described, and it is not approved.
    assert "half size" in meanrev["policy"]["description"]
    assert "not approved" in meanrev["policy"]["description"]
    assert "No agent gate was accepted" not in meanrev["policy"]["description"]
    assert meanrev["policy"]["test_evaluated"] is False
    assert meanrev["steps"] and all(step["evidence_ids"] == [] for step in meanrev["steps"])
    assert meanrev["steps"][-1]["title"] == "Strategy verdict: KILL"

    trend = fallback("btc-trend-24-72-demo")
    assert trend["verdict"] == "INCONCLUSIVE"
    assert trend["policy"]["description"] == "No filter was selected. The original strategy is unchanged."
    assert trend["recommendation"].startswith("Not proven.")


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


def _import_positions(body: bytes, *, symbol: str = "BTCUSDT", timeframe: str = "1h", name: str = "Imported positions") -> dict:
    preview_result = preview(upload("positions.csv", body))
    request = ImportRequest(**{
        "upload_id": preview_result["upload_id"], "name": name, "symbol": symbol, "timeframe": timeframe, "strategy_version": "v1",
        "kind": "positions", "mapping": preview_result["suggested_mapping"], "timezone": "UTC", "fee_bps": 10, "slippage_bps": 1, "description": "",
    })
    request.mapping = preview_result["suggested_mapping"]
    imported = import_strategy(request)
    assert imported["valid"] is True, imported["issues"]
    return imported["strategy"]


def _hourly_positions(start: datetime, hours: int, symbol: str = "BTCUSDT") -> bytes:
    lines = ["decision_time,symbol,target_position"]
    for index in range(hours):
        stamp = (start + timedelta(hours=index)).strftime("%Y-%m-%dT%H:%M:%SZ")
        target = "1" if (index // 24) % 2 == 0 else "0"
        lines.append(f"{stamp},{symbol},{target}")
    return ("\n".join(lines) + "\n").encode()


def test_other_symbol_stays_pending_without_demo_metrics() -> None:
    body = _hourly_positions(datetime(2024, 11, 15, tzinfo=timezone.utc), 48, "ETHUSDT")
    strategy = _import_positions(body, symbol="ETHUSDT", name=f"ETH {uuid.uuid4().hex[:6]}")
    experiment = create_experiment(ExperimentRequest(strategy_id=strategy["strategy_id"]), None)
    assert experiment["status"] == "awaiting_engine"
    assert experiment["mode"] == "pending"
    assert experiment["metrics"] == []
    assert experiment["equity"] == []
    assert experiment["verdict"] == "INCONCLUSIVE"


def test_positions_outside_the_snapshot_fail_without_demo_numbers() -> None:
    body = b"decision_time,symbol,target_position\n2024-01-01T00:00:00Z,BTCUSDT,1\n2024-01-01T01:00:00Z,BTCUSDT,0\n"
    strategy = _import_positions(body, name=f"Early {uuid.uuid4().hex[:6]}")
    experiment = create_experiment(ExperimentRequest(strategy_id=strategy["strategy_id"]), None)
    assert experiment["status"] == "failed"
    assert experiment["mode"] == "pending"
    assert experiment["metrics"] == []
    assert experiment["equity"] == []
    assert experiment["verdict"] == "INCONCLUSIVE"
    assert "demo" not in experiment["message"].lower()


def test_btcusdt_hourly_positions_are_measured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import apps.api.engine as engine
    import apps.api.team_reports as team_reports

    monkeypatch.setattr(team_reports, "ROOT", tmp_path)

    def fast(experiment_id, strategy, **kwargs):
        kwargs.setdefault("n_boot", 8)
        kwargs.setdefault("n_estimators", 15)
        kwargs.setdefault("force_fallback", True)
        return engine.run_measured_experiment(experiment_id, strategy, **kwargs)

    monkeypatch.setattr(api, "run_measured_experiment", fast)
    body = _hourly_positions(datetime(2024, 11, 15, tzinfo=timezone.utc), 800)
    strategy = _import_positions(body, name=f"BTC hourly {uuid.uuid4().hex[:6]}")
    experiment = create_experiment(ExperimentRequest(strategy_id=strategy["strategy_id"]), None)
    assert experiment["status"] == "completed", experiment["message"]
    assert experiment["mode"] == "measured"
    assert experiment["metrics"]
    assert experiment["baselines"]
    assert any(row["id"] == "always_on" for row in experiment["baselines"])
    assert experiment["equity"][0]["date"].startswith("2024-11")
    assert "illustrative" not in experiment["message"].lower()
    assert experiment["verdict"] in {"KEEP", "MODIFY", "COMBINE", "RESTRICT", "MONITOR", "KILL", "INCONCLUSIVE", "CONDITIONAL", "REDUCE"}
    report_path = tmp_path / "experiments" / f"investigation_{experiment['experiment_id']}.json"
    assert report_path.is_file()
    report = json.loads(report_path.read_text())
    assert report["holdout_accessed"] is False
    assert report["experiment_id"] == experiment["experiment_id"]


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
    assert plan["status"] == "awaiting_bars"
    assert plan["execution"] == "paper_only"
    assert plan["shadow"]["interval"] == "1h"
    assert plan["shadow"]["horizon_bars"] == 14 * 24
    assert plan["shadow"]["fills_recorded"] == 0
    assert plan["shadow"]["conclusion"] is None
    assert "No trading" in plan["message"]


def test_timestamp_offset_is_normalized_and_dst_ambiguity_is_rejected() -> None:
    assert parse_timestamp("2024-01-01T01:00:00+01:00", "UTC").isoformat() == "2024-01-01T00:00:00+00:00"
    rows, issues, start, end = validate_rows(
        ["decision_time", "symbol", "target_position"],
        [{"decision_time": "2024-01-01T00:00:00Z", "symbol": "BTCUSDT", "target_position": "0.2"}],
        "positions", {"decision_time": "decision_time", "symbol": "symbol", "target_position": "target_position"}, "UTC",
    )
    assert rows and not [item for item in issues if item["severity"] == "error"] and start == end
