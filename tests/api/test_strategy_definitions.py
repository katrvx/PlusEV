from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import apps.api.main as api
from apps.api.strategy_definitions import (
    StrategyDefinitionRequest,
    definition_hash,
    definition_json_bytes,
    definition_payload,
    template_definition,
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


def ema_definition(**overrides) -> dict:
    payload = {
        "schema_version": "1",
        "name": "BTC momentum cross",
        "symbol": "btcusdt",
        "timeframe": "1h",
        "strategy_version": "v1.2.0",
        "rule": {"family": "ema_crossover", "fast_period": 20, "slow_period": 50, "long_position": 1, "flat_position": 0},
        "period": {"start": "2024-01-01T00:00:00Z", "end": "2024-02-01T00:00:00Z"},
        "market_data": {"source": "awaiting_upload", "upload_id": None},
        "costs": {"timezone": "UTC", "fee_bps": 5, "slippage_bps": 2, "execution": "next_bar_open"},
        "description": "Fast EMA above slow EMA.",
    }
    payload.update(overrides)
    return payload


def test_definition_record_saves_portable_hash_and_pending_strategy() -> None:
    definition = StrategyDefinitionRequest.model_validate(ema_definition())
    strategy = api.persist_strategy_definition(definition)
    assert strategy["source"] == "strategy_definition"
    assert strategy["status"] == "draft"
    assert strategy["readiness"] == "awaiting_market_data"
    assert strategy["row_count"] == 0
    assert strategy["date_start"] == strategy["date_end"] == ""
    assert strategy["dataset_hash"] == ""
    assert strategy["definition_hash"].startswith("sha256:")

    persisted = api.db_get("strategies", "strategy_id", strategy["strategy_id"])
    assert persisted is not None
    definition_file = Path(persisted["definition_path"])
    assert definition_file.exists()
    assert definition_file.read_bytes() == definition_json_bytes(definition)

    pending = api.create_experiment(api.ExperimentRequest(strategy_id=strategy["strategy_id"]), None)
    assert pending["status"] == "awaiting_engine"
    assert pending["mode"] == "pending"
    assert pending["metrics"] == []
    assert pending["equity"] == []
    assert pending["dataset_hash"] == ""
    assert "illustrative metrics" in pending["recommendation"]


def test_definition_download_round_trips_canonical_definition() -> None:
    definition = StrategyDefinitionRequest.model_validate(ema_definition())
    strategy = api.persist_strategy_definition(definition)
    response = api.download_strategy_definition(strategy["strategy_id"])
    assert response.media_type == "application/json"
    assert json.loads(response.body) == definition_payload(definition)
    assert response.headers["content-disposition"].endswith(f"{strategy['strategy_id']}-definition.json")
    assert strategy["definition_hash"] == definition_hash(definition)


@pytest.mark.parametrize(
    "rule",
    [
        {"family": "ema_crossover", "fast_period": 50, "slow_period": 20, "long_position": 1, "flat_position": 0},
        {"family": "ema_crossover", "fast_period": 0, "slow_period": 20, "long_position": 1, "flat_position": 0},
        {"family": "rsi_mean_reversion", "period": 14, "entry_below": 70, "exit_above": 30, "long_position": 1, "flat_position": 0},
        {"family": "ema_crossover", "fast_period": 20, "slow_period": 50, "long_position": 1, "flat_position": 0, "execute": "python"},
    ],
)
def test_definition_rejects_invalid_or_unknown_rule_fields(rule: dict) -> None:
    with pytest.raises(ValidationError):
        StrategyDefinitionRequest.model_validate({**ema_definition(), "rule": rule})


def test_rsi_definition_accepts_bounded_rule_and_template_is_valid() -> None:
    rsi = StrategyDefinitionRequest.model_validate({
        **ema_definition(),
        "rule": {"family": "rsi_mean_reversion", "period": 14, "entry_below": 30, "exit_above": 55, "long_position": 1, "flat_position": 0},
    })
    assert rsi.rule.family == "rsi_mean_reversion"
    template = template_definition()
    assert template.rule.family == "ema_crossover"
    assert definition_hash(template) == definition_hash(StrategyDefinitionRequest.model_validate(definition_payload(template)))


def test_definition_payload_validation_rejects_non_object_and_unknown_fields() -> None:
    with pytest.raises(HTTPException) as invalid:
        api.validate_strategy_definition_payload(["not", "an", "object"])
    assert invalid.value.status_code == 422
    with pytest.raises(ValidationError):
        StrategyDefinitionRequest.model_validate({**ema_definition(), "unexpected": True})


def test_definition_is_long_only_and_market_data_attachment_is_not_claimed() -> None:
    with pytest.raises(ValidationError):
        StrategyDefinitionRequest.model_validate({
            **ema_definition(),
            "rule": {"family": "ema_crossover", "fast_period": 20, "slow_period": 50, "long_position": -1, "flat_position": 0},
        })
    with pytest.raises(ValidationError):
        StrategyDefinitionRequest.model_validate({
            **ema_definition(),
            "market_data": {"source": "user_upload", "upload_id": "upl_12345678"},
        })


def test_definition_rejects_future_period_and_unsafe_symbol() -> None:
    future_start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat().replace("+00:00", "Z")
    future_end = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat().replace("+00:00", "Z")
    with pytest.raises(ValidationError):
        StrategyDefinitionRequest.model_validate({
            **ema_definition(),
            "period": {"start": future_start, "end": future_end},
        })
    with pytest.raises(ValidationError):
        StrategyDefinitionRequest.model_validate({**ema_definition(), "symbol": "BTC USDT"})
