from __future__ import annotations

import io
import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError

import apps.api.main as api


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


def preview_positions(value: str = "0.5", *, symbol: str = "BTCUSDT", timestamp: str = "2024-01-01T00:00:00Z") -> dict:
    body = f"decision_time,symbol,target_position\n{timestamp},{symbol},{value}\n".encode()
    return api.preview(upload("positions.csv", body))


def import_preview(payload: dict, *, symbol: str = "BTCUSDT", mapping: dict[str, str] | None = None) -> dict:
    request = api.ImportRequest(
        upload_id=payload["upload_id"], name="Contract test", symbol=symbol,
        timeframe="1h", strategy_version="v1", kind="positions",
        mapping=mapping or payload["suggested_mapping"], timezone="UTC",
        fee_bps=5, slippage_bps=2,
    )
    return api.import_strategy(request)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "1.01", "-1.01"])
def test_rejects_nonfinite_and_out_of_range_exposure(value: str) -> None:
    result = import_preview(preview_positions(value))
    assert result["valid"] is False
    assert any(item["code"] == "invalid_row" for item in result["issues"])


def test_rejects_duplicate_and_future_position_rows() -> None:
    body = b"decision_time,symbol,target_position\n2024-01-01T00:00:00Z,BTCUSDT,0\n2024-01-01T00:00:00Z,BTCUSDT,1\n"
    payload = api.preview(upload("duplicates.csv", body))
    result = import_preview(payload)
    assert result["valid"] is False
    assert any("duplicate" in item["message"] for item in result["issues"])

    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat().replace("+00:00", "Z")
    future_result = import_preview(preview_positions("0", timestamp=future))
    assert future_result["valid"] is False
    assert any("future" in item["message"] for item in future_result["issues"])


def test_rejects_missing_mapping_and_metadata_symbol_mismatch() -> None:
    payload = preview_positions()
    mapping = dict(payload["suggested_mapping"])
    mapping.pop("target_position")
    missing = import_preview(payload, mapping=mapping)
    assert missing["valid"] is False
    assert any(item["code"] == "missing_mapping" for item in missing["issues"])

    mismatch = import_preview(preview_positions(symbol="ETHUSDT"), symbol="BTCUSDT")
    assert mismatch["valid"] is False
    assert any(item["code"] == "symbol_mismatch" for item in mismatch["issues"])


def test_import_persists_canonical_rows_source_mapping_and_hashes() -> None:
    payload = preview_positions()
    result = import_preview(payload)
    assert result["valid"] is True
    strategy = result["strategy"]
    canonical = Path(strategy["canonical_data_path"])
    assert canonical.exists()
    assert strategy["source_mapping"] == payload["suggested_mapping"]
    assert strategy["raw_data_hash"] == strategy["dataset_hash"]
    assert strategy["canonical_data_hash"] == api.hashlib.sha256(canonical.read_bytes()).hexdigest()
    assert json.loads(canonical.read_text())[0]["symbol"] == "BTCUSDT"


def test_metadata_whitespace_rejected() -> None:
    with pytest.raises(ValidationError):
        api.ImportRequest(
            upload_id="upl_test", name=" ", symbol="BTCUSDT", timeframe="1h",
            strategy_version="v1", kind="positions", mapping={}, timezone="UTC",
        )


def test_timestamp_offsets_and_dst_edges() -> None:
    assert api.parse_timestamp("2024-01-01T01:00:00+01:00", "UTC").isoformat() == "2024-01-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="ambiguous or nonexistent"):
        api.parse_timestamp("2024-10-27T01:30:00", "Europe/London")
    with pytest.raises(ValueError, match="ambiguous or nonexistent"):
        api.parse_timestamp("2024-03-31T01:30:00", "Europe/London")


def test_parquet_timestamp_preview_is_json_safe_and_importable() -> None:
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    table = pa.table({
        "decision_time": pa.array([datetime(2024, 1, 1, tzinfo=timezone.utc)], type=pa.timestamp("us", tz="UTC")),
        "symbol": ["BTCUSDT"], "target_position": [0.25],
    })
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    payload = api.preview(upload("signals.parquet", buffer.getvalue()))
    assert payload["detected_kind"] == "positions"
    assert isinstance(payload["rows"][0]["decision_time"], str)
    result = api.import_strategy(api.ImportRequest(
        upload_id=payload["upload_id"], name="Parquet strategy", symbol="BTCUSDT",
        timeframe="1h", strategy_version="v1", kind="positions",
        mapping=payload["suggested_mapping"], timezone="UTC", fee_bps=5, slippage_bps=2,
    ))
    assert result["valid"] is True


def test_queue_transition_and_frozen_paper_snapshot() -> None:
    background = api.BackgroundTasks()
    queued = api.create_experiment(api.ExperimentRequest(strategy_id="demo_btc_trend_v1"), background)
    assert queued["status"] == "queued" and background.tasks
    task = background.tasks[0]
    task.func(*task.args, **task.kwargs)
    completed = api.get_experiment(queued["experiment_id"])
    assert completed["status"] == "completed"
    plan = api.create_paper_test(api.PaperTestRequest(experiment_id=completed["experiment_id"], duration_days=14, approved=True))
    assert plan["execution"] == "paper_only"
    assert plan["snapshot"]["dataset_hash"] == completed["dataset_hash"]
    assert plan["snapshot"]["policy"] == completed["policy"]
    assert plan["snapshot"]["windows"] == completed["windows"]

    altered = dict(completed, experiment_id="exp_unfrozen", policy=dict(completed["policy"], holdout_frozen=False))
    api.db_insert("experiments", altered["experiment_id"], altered)
    with pytest.raises(HTTPException) as error:
        api.create_paper_test(api.PaperTestRequest(experiment_id="exp_unfrozen", duration_days=14, approved=True))
    assert error.value.status_code == 409


def test_demo_curve_endpoints_window_and_evidence_are_consistent() -> None:
    experiment = api.experiments(strategy_id="demo_btc_trend_v1")[0]
    curve = experiment["equity"]
    test_start, test_end = experiment["windows"]["test"].split(" to ")
    dates = [datetime.fromisoformat(point["date"].replace("Z", "+00:00")) for point in curve]
    start_bound = datetime.fromisoformat(test_start.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
    end_bound = datetime.fromisoformat(test_end.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
    assert dates[0] == start_bound
    assert dates[-1] == end_bound
    assert dates == sorted(dates)
    assert all(start_bound <= date <= end_bound for date in dates)
    assert curve[0]["base"] > 0 and curve[-1]["base"] > 0
    assert curve[0]["cash"] == 100 and curve[-1]["cash"] == 100
    assert len(curve) == 45
    evidence_ids = {item["id"] for item in experiment["evidence"]}
    assert evidence_ids
    assert all(regime["evidence_id"] in evidence_ids for regime in experiment["regimes"])
    assert all(step_evidence in evidence_ids for step in experiment["steps"] for step_evidence in step["evidence_ids"])
