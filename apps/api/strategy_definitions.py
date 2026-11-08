"""Validated, non-executable strategy definitions for Part C.

Definitions describe a small, versioned rule family.  They are stored as
portable JSON and remain drafts until real market data and the deterministic
evaluator are connected.  This module deliberately contains no code loading,
expression evaluation, or market-data fabrication.

Rule semantics for the eventual evaluator are intentionally plain:

* ``ema_crossover`` uses only closed-bar prices available at decision time;
  after warmup, it targets long position ``1`` when fast EMA is above slow EMA
  and flat position ``0`` otherwise.
* ``rsi_mean_reversion`` uses a closed-bar RSI; it enters long below
  ``entry_below`` and exits when RSI is above ``exit_above``.  The evaluator
  must preserve that state between bars rather than silently treating the
  thresholds as an unrelated one-bar mask.

Both families execute on the next eligible bar open when an evaluator exists.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictInt, StrictStr, field_validator, model_validator


DEFINITION_SCHEMA_VERSION = "1"
DEFINITION_ENGINE_VERSION = "declarative-rules-v1"
MAX_DEFINITION_BYTES = 64 * 1024
TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _nonblank(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} must not be blank")
    return cleaned


def _parse_period_timestamp(value: str, field: str) -> datetime:
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    normalized = parsed.astimezone(timezone.utc)
    if normalized > datetime.now(timezone.utc) + timedelta(minutes=2):
        raise ValueError(f"{field} must not be in the future")
    return normalized


class DefinitionPeriod(StrictModel):
    start: StrictStr | None = None
    end: StrictStr | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "DefinitionPeriod":
        if (self.start is None) != (self.end is None):
            raise ValueError("period.start and period.end must be supplied together")
        if self.start is None or self.end is None:
            return self
        start = _parse_period_timestamp(self.start, "period.start")
        end = _parse_period_timestamp(self.end, "period.end")
        if end <= start:
            raise ValueError("period.end must be after period.start")
        return self


class MarketDataSpec(StrictModel):
    # A candle attachment contract does not exist yet.  Keep this explicit so
    # a definition cannot imply that a market file was validated by merely
    # carrying an upload id.
    source: Literal["awaiting_upload"] = "awaiting_upload"
    upload_id: StrictStr | None = None

    @field_validator("upload_id")
    @classmethod
    def validate_upload_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not re.fullmatch(r"upl_[A-Za-z0-9]{8,90}", cleaned):
            raise ValueError("market_data.upload_id must be a valid upload identifier")
        return cleaned

    @model_validator(mode="after")
    def validate_source(self) -> "MarketDataSpec":
        if self.upload_id is not None:
            raise ValueError("market_data.upload_id is not supported until candle attachment validation exists")
        return self


class CostAssumptions(StrictModel):
    timezone: StrictStr = "UTC"
    fee_bps: FiniteFloat = Field(default=5.0, ge=0.0, le=10_000.0)
    slippage_bps: FiniteFloat = Field(default=2.0, ge=0.0, le=10_000.0)
    execution: Literal["next_bar_open"] = "next_bar_open"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        cleaned = _nonblank(value, "costs.timezone")
        if cleaned.upper() in {"UTC", "ETC/UTC", "GMT", "ETC/GMT"}:
            return "UTC"
        try:
            ZoneInfo(cleaned)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"Unknown IANA timezone: {cleaned}") from None
        return cleaned

    @field_validator("fee_bps", "slippage_bps", mode="before")
    @classmethod
    def validate_cost_number(cls, value: object, info) -> float:
        return _finite_number(value, f"costs.{info.field_name}")


class PositionBounds(StrictModel):
    long_position: FiniteFloat = Field(default=1.0, ge=-1.0, le=1.0)
    flat_position: FiniteFloat = Field(default=0.0, ge=-1.0, le=1.0)

    @field_validator("long_position", "flat_position", mode="before")
    @classmethod
    def validate_position_number(cls, value: object, info) -> float:
        return _finite_number(value, info.field_name)

    @model_validator(mode="after")
    def positions_differ(self) -> "PositionBounds":
        if self.long_position != 1.0 or self.flat_position != 0.0:
            raise ValueError("v1 declarative rules are long-only: long_position must be 1 and flat_position must be 0")
        return self


class EMACrossoverRule(PositionBounds):
    family: Literal["ema_crossover"]
    fast_period: StrictInt = Field(ge=2, le=1_000)
    slow_period: StrictInt = Field(ge=3, le=2_000)

    @model_validator(mode="after")
    def periods_are_ordered(self) -> "EMACrossoverRule":
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be less than slow_period")
        return self


class RSIMeanReversionRule(PositionBounds):
    family: Literal["rsi_mean_reversion"]
    period: StrictInt = Field(ge=2, le=1_000)
    entry_below: FiniteFloat = Field(ge=0.0, le=100.0)
    exit_above: FiniteFloat = Field(ge=0.0, le=100.0)

    @field_validator("entry_below", "exit_above", mode="before")
    @classmethod
    def validate_rsi_number(cls, value: object, info) -> float:
        return _finite_number(value, info.field_name)

    @model_validator(mode="after")
    def thresholds_are_ordered(self) -> "RSIMeanReversionRule":
        if self.entry_below >= self.exit_above:
            raise ValueError("entry_below must be less than exit_above")
        return self


RuleDefinition = Annotated[Union[EMACrossoverRule, RSIMeanReversionRule], Field(discriminator="family")]


class StrategyDefinitionRequest(StrictModel):
    schema_version: Literal["1"] = DEFINITION_SCHEMA_VERSION
    name: StrictStr = Field(min_length=1, max_length=120)
    symbol: StrictStr = Field(min_length=1, max_length=40)
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d"]
    strategy_version: StrictStr = Field(min_length=1, max_length=100)
    rule: RuleDefinition
    period: DefinitionPeriod = Field(default_factory=DefinitionPeriod)
    market_data: MarketDataSpec = Field(default_factory=MarketDataSpec)
    costs: CostAssumptions = Field(default_factory=CostAssumptions)
    description: StrictStr = Field(default="", max_length=1_000)

    @field_validator("name", "symbol", "strategy_version")
    @classmethod
    def validate_identity(cls, value: str, info) -> str:
        return _nonblank(value, info.field_name)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{0,39}", normalized):
            raise ValueError("symbol must use letters, numbers, dots, underscores, slashes or hyphens")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()


def definition_payload(definition: StrategyDefinitionRequest) -> dict:
    """Return the stable JSON-compatible representation used for hashing/storage."""
    return definition.model_dump(mode="json", exclude_none=False)


def definition_json_bytes(definition: StrategyDefinitionRequest) -> bytes:
    return json.dumps(
        definition_payload(definition),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def definition_hash(definition: StrategyDefinitionRequest) -> str:
    return f"sha256:{hashlib.sha256(definition_json_bytes(definition)).hexdigest()}"


def strategy_record(
    definition: StrategyDefinitionRequest,
    strategy_id: str,
    created_at: str,
    definition_path: str,
) -> dict:
    """Build a Strategy-shaped draft without inventing position rows or dates."""
    digest = definition_hash(definition)
    payload = definition_payload(definition)
    return {
        "strategy_id": strategy_id,
        "name": definition.name,
        "symbol": definition.symbol,
        "timeframe": definition.timeframe,
        "strategy_version": definition.strategy_version,
        "source": "strategy_definition",
        # Keep the existing Strategy shape compatible while making the draft
        # explicit. No generated positions are claimed until market data exists.
        "kind": "positions",
        "status": "draft",
        "readiness": "awaiting_market_data",
        "execution_status": "definition_saved",
        "row_count": 0,
        "date_start": "",
        "date_end": "",
        "dataset_hash": "",
        "market_data_hash": None,
        "definition_hash": digest,
        "definition_schema_version": definition.schema_version,
        "definition_path": definition_path,
        "definition": payload,
        "created_at": created_at,
        "assumptions": {
            "timezone": definition.costs.timezone,
            "fee_bps": float(definition.costs.fee_bps),
            "slippage_bps": float(definition.costs.slippage_bps),
            "execution": definition.costs.execution,
            "description": definition.description,
        },
    }


def template_definition() -> StrategyDefinitionRequest:
    return StrategyDefinitionRequest(
        name="BTC EMA crossover",
        symbol="BTCUSDT",
        timeframe="1h",
        strategy_version="v1",
        rule={"family": "ema_crossover", "fast_period": 20, "slow_period": 50, "long_position": 1.0, "flat_position": 0.0},
        description="Long when the fast EMA is above the slow EMA; otherwise stay flat.",
    )
