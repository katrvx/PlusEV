"""Part C API for Keep or Kill.

Uploaded strategy data is validated and stored, but does not receive fabricated
research results. The demo uses a clearly labelled deterministic fixture until
Parts A and B connect their real point-in-time evaluator and research agents.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import sqlite3
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from .strategy_definitions import (
    MAX_DEFINITION_BYTES,
    StrategyDefinitionRequest,
    definition_json_bytes,
    definition_payload,
    strategy_record,
    template_definition,
)
from .judge_example import (
    DEFAULT_NATIVE_STRATEGY_ID,
    NATIVE_REPORT_STRATEGY_IDS,
    build_virtual_bundle,
    is_virtual_experiment,
    is_virtual_strategy,
    strategy_id_for_experiment,
)
from .team_reports import router as team_reports_router

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "local"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "keep_or_kill.sqlite3"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PREVIEW_ROWS = 10
MAX_IMPORT_ROWS = 250_000
_db_lock = threading.RLock()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def loads(value: str) -> Any:
    return json.loads(value)


def connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _db_lock, connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS strategies (
              strategy_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
              raw_path TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS uploads (
              upload_id TEXT PRIMARY KEY, filename TEXT NOT NULL,
              payload TEXT NOT NULL, raw_path TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiments (
              experiment_id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL,
              payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS experiments_strategy_idx
              ON experiments(strategy_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS paper_tests (
              paper_test_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL,
              payload TEXT NOT NULL, approved_at TEXT NOT NULL
            );
            """
        )


def db_insert(table: str, key: str, payload: dict[str, Any]) -> None:
    now = payload.get("created_at") or payload.get("approved_at") or iso(utc_now())
    with _db_lock, connection() as conn:
        if table == "strategies":
            conn.execute("INSERT OR REPLACE INTO strategies VALUES (?,?,?,?)", (key, dumps(payload), payload.get("raw_path"), now))
        elif table == "uploads":
            conn.execute("INSERT OR REPLACE INTO uploads VALUES (?,?,?,?,?)", (key, payload["filename"], dumps(payload), payload["raw_path"], now))
        elif table == "experiments":
            conn.execute("INSERT OR REPLACE INTO experiments VALUES (?,?,?,?)", (key, payload["strategy_id"], dumps(payload), now))
        elif table == "paper_tests":
            conn.execute("INSERT OR REPLACE INTO paper_tests VALUES (?,?,?,?)", (key, payload["experiment_id"], dumps(payload), now))
        else:
            raise ValueError(f"unsupported table: {table}")


def db_get(table: str, key_column: str, key: str) -> dict[str, Any] | None:
    with _db_lock, connection() as conn:
        row = conn.execute(f"SELECT payload FROM {table} WHERE {key_column} = ?", (key,)).fetchone()
    return loads(row["payload"]) if row else None


def db_list(table: str, order: str = "created_at DESC") -> list[dict[str, Any]]:
    with _db_lock, connection() as conn:
        rows = conn.execute(f"SELECT payload FROM {table} ORDER BY {order}").fetchall()
    return [loads(row["payload"]) for row in rows]


def issue(severity: Literal["error", "warning"], code: str, message: str, row: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if row is not None:
        result["row"] = row
    return result


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", Path(name or "upload.csv").name)[:120] or "upload.csv"


POSITION_ALIASES = {
    "decision_time": {"decision_time", "timestamp", "time", "datetime", "date", "signal_time", "bar_time"},
    "symbol": {"symbol", "ticker", "asset", "instrument", "pair"},
    "target_position": {"target_position", "position", "target_exposure", "exposure", "signal", "weight"},
}
TRADE_ALIASES = {
    "entry_time": {"entry_time", "entry", "entry_date", "open_time", "open_datetime"},
    "exit_time": {"exit_time", "exit", "exit_date", "close_time", "close_datetime"},
    "symbol": {"symbol", "ticker", "asset", "instrument", "pair"},
    "side": {"side", "direction", "position_side", "trade_type"},
    "quantity": {"quantity", "qty", "size", "amount", "volume"},
    "entry_price": {"entry_price", "entry_px", "open_price", "buy_price"},
    "exit_price": {"exit_price", "exit_px", "close_price", "sell_price"},
}


def normalized_column(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def suggest_mapping(columns: list[str], kind: str | None = None) -> tuple[dict[str, str], str]:
    normalized = {normalized_column(column): column for column in columns}

    def guess(aliases: dict[str, set[str]]) -> dict[str, str]:
        result: dict[str, str] = {}
        for canonical, values in aliases.items():
            for alias in values:
                if alias in normalized:
                    result[canonical] = normalized[alias]
                    break
        return result

    positions, trades = guess(POSITION_ALIASES), guess(TRADE_ALIASES)
    if kind == "positions":
        return positions, "positions"
    if kind == "trades":
        return trades, "trades"
    return (positions, "positions") if len(positions) >= len(trades) else (trades, "trades")


def read_upload(content: bytes, filename: str) -> tuple[list[str], list[dict[str, Any]], int, list[dict[str, Any]]]:
    if len(content) > MAX_UPLOAD_BYTES:
        return [], [], 0, [issue("error", "file_too_large", "Upload exceeds the 10 MB limit.")]
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".parquet", ".pq"}:
        return [], [], 0, [issue("error", "unsupported_file_type", "Upload a CSV or Parquet file.")]
    if suffix in {".parquet", ".pq"}:
        try:
            import pyarrow.parquet as parquet  # type: ignore
            metadata = parquet.read_metadata(io.BytesIO(content))
            if metadata.num_rows > MAX_IMPORT_ROWS:
                return [], [], 0, [issue("error", "too_many_rows", "Import at most 250,000 rows per file.")]
            table = parquet.read_table(io.BytesIO(content))
            if len(set(table.column_names)) != len(table.column_names):
                return [], [], 0, [issue("error", "duplicate_columns", "Column names must be unique.")]
            return [str(name) for name in table.column_names], [json_safe(row) for row in table.slice(0, MAX_PREVIEW_ROWS).to_pylist()], table.num_rows, []
        except ImportError:
            return [], [], 0, [issue("error", "parquet_dependency_missing", "Parquet support requires pyarrow on the API worker.")]
        except Exception as exc:
            return [], [], 0, [issue("error", "parquet_read_error", f"Could not read Parquet: {exc}")]
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [], 0, [issue("error", "invalid_encoding", "CSV must be UTF-8 encoded.")]
    if not text.strip():
        return [], [], 0, [issue("error", "empty_file", "The uploaded file has no rows.")]
    try:
        reader = csv.DictReader(io.StringIO(text))
        columns = [str(column).strip() for column in (reader.fieldnames or [])]
        if not columns:
            return [], [], 0, [issue("error", "missing_header", "CSV must include a header row.")]
        if any(not name for name in columns) or len(set(columns)) != len(columns):
            return [], [], 0, [issue("error", "invalid_columns", "CSV column names must be non-empty and unique.")]
        reader.fieldnames = columns
        rows: list[dict[str, Any]] = []
        count = 0
        for row in reader:
            count += 1
            if count > MAX_IMPORT_ROWS:
                return [], [], 0, [issue("error", "too_many_rows", "Import at most 250,000 rows per file.")]
            if None in row or any(value is None for value in row.values()):
                return columns, rows, count, [issue("error", "ragged_row", "Every row must have the same number of fields as the header.", count + 1)]
            if len(rows) < MAX_PREVIEW_ROWS:
                rows.append({str(key): (value if value != "" else None) for key, value in row.items() if key is not None})
        problems = [issue("error", "no_data_rows", "CSV has a header but no data rows.")] if count == 0 else []
        return columns, rows, count, problems
    except csv.Error as exc:
        return [], [], 0, [issue("error", "csv_parse_error", f"Could not read CSV: {exc}")]


def valid_zone(name: str) -> ZoneInfo | timezone:
    if name.strip().upper() in {"UTC", "ETC/UTC", "GMT", "ETC/GMT"}:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Unknown IANA timezone: {name}") from None


def json_safe(value: Any) -> Any:
    """Convert Parquet scalar values to values accepted by JSON responses."""
    if isinstance(value, datetime):
        return iso(value) if value.tzinfo else value.isoformat()
    if isinstance(value, (date, Decimal)):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def parse_timestamp(raw: Any, timezone_name: str) -> datetime:
    if raw is None or str(raw).strip() == "":
        raise ValueError("timestamp is empty")
    value = str(raw).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = None
        for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(str(raw).strip(), fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError(f"invalid timestamp: {raw}") from None
    if parsed.tzinfo is None:
        zone = valid_zone(timezone_name)
        # A DST transition can map one wall-clock value to two instants. Reject it.
        if parsed.replace(tzinfo=zone, fold=0).utcoffset() != parsed.replace(tzinfo=zone, fold=1).utcoffset():
            raise ValueError(f"ambiguous or nonexistent local timestamp: {raw}")
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(timezone.utc)


def finite_float(raw: Any, field: str) -> float:
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be numeric") from None
    if not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    return value


def validate_rows(columns: list[str], rows: list[dict[str, Any]], kind: str, mapping: dict[str, str], timezone_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None, str | None]:
    aliases = POSITION_ALIASES if kind == "positions" else TRADE_ALIASES if kind == "trades" else {}
    if not aliases:
        return [], [issue("error", "invalid_kind", "kind must be positions or trades")], None, None
    required = list(aliases)
    problems: list[dict[str, Any]] = []
    missing = [field for field in required if not mapping.get(field)]
    unknown = [field for field in required if mapping.get(field) not in columns]
    if missing:
        problems.append(issue("error", "missing_mapping", f"Map required fields: {', '.join(missing)}"))
    if unknown:
        problems.append(issue("error", "unknown_mapping", f"Mapped source columns do not exist: {', '.join(unknown)}"))
    assigned = [mapping[field] for field in required if field in mapping]
    if len(set(assigned)) != len(assigned):
        problems.append(issue("error", "duplicate_mapping", "Each required field must map to a different source column."))
    try:
        valid_zone(timezone_name)
    except ValueError as exc:
        problems.append(issue("error", "invalid_timezone", str(exc)))
    if problems:
        return [], problems, None, None
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    previous: datetime | None = None
    for line, row in enumerate(rows, start=2):
        try:
            if kind == "positions":
                timestamp = parse_timestamp(row.get(mapping["decision_time"]), timezone_name)
                symbol = str(row.get(mapping["symbol"]) or "").strip().upper()
                target = finite_float(row.get(mapping["target_position"]), "target_position")
                if not symbol:
                    raise ValueError("symbol is empty")
                if target < -1 or target > 1:
                    raise ValueError("target_position must be between -1 and 1")
                key = (symbol, iso(timestamp))
                if key in seen:
                    raise ValueError("duplicate symbol and decision_time")
                seen.add(key)
                item = {"decision_time": iso(timestamp), "symbol": symbol, "target_position": target}
            else:
                entry = parse_timestamp(row.get(mapping["entry_time"]), timezone_name)
                exit_time = parse_timestamp(row.get(mapping["exit_time"]), timezone_name)
                if exit_time <= entry:
                    raise ValueError("exit_time must be after entry_time")
                if exit_time > utc_now() + timedelta(minutes=2):
                    raise ValueError("exit_time is in the future")
                symbol = str(row.get(mapping["symbol"]) or "").strip().upper()
                side = str(row.get(mapping["side"]) or "").strip().lower()
                if side not in {"long", "short"}:
                    raise ValueError("side must be long or short")
                quantity = finite_float(row.get(mapping["quantity"]), "quantity")
                entry_price, exit_price = finite_float(row.get(mapping["entry_price"]), "entry_price"), finite_float(row.get(mapping["exit_price"]), "exit_price")
                if not symbol or quantity <= 0 or entry_price <= 0 or exit_price <= 0:
                    raise ValueError("symbol, quantity and prices must be positive/present")
                item = {"entry_time": iso(entry), "exit_time": iso(exit_time), "symbol": symbol, "side": side, "quantity": quantity, "entry_price": entry_price, "exit_price": exit_price}
                timestamp = entry
            if timestamp > utc_now() + timedelta(minutes=2):
                raise ValueError("timestamp is in the future")
            if previous and timestamp < previous and not any(item.get("code") == "nonmonotonic_source" for item in problems):
                problems.append(issue("warning", "nonmonotonic_source", "Source timestamps are not monotonic; records are stored in source order."))
            previous = timestamp
            normalized.append(item)
        except ValueError as exc:
            problems.append(issue("error", "invalid_row", str(exc), line))
    if not normalized:
        problems.append(issue("error", "no_valid_rows", "No valid rows remain after validation."))
        return [], problems, None, None
    if kind == "positions":
        dates = [datetime.fromisoformat(row["decision_time"].replace("Z", "+00:00")) for row in normalized]
    else:
        dates = [datetime.fromisoformat(row["entry_time"].replace("Z", "+00:00")) for row in normalized] + [datetime.fromisoformat(row["exit_time"].replace("Z", "+00:00")) for row in normalized]
    return normalized, problems, iso(min(dates)), iso(max(dates))


def strategy_payload(strategy_id: str, name: str, symbol: str, timeframe: str, version: str, source: str, kind: str, status: str, row_count: int, date_start: str, date_end: str, dataset_hash: str, timezone_name: str, fee_bps: float, slippage_bps: float, description: str) -> dict[str, Any]:
    return {"strategy_id": strategy_id, "name": name, "symbol": symbol, "timeframe": timeframe, "strategy_version": version, "source": source, "kind": kind, "status": status, "row_count": row_count, "date_start": date_start, "date_end": date_end, "dataset_hash": dataset_hash, "created_at": iso(utc_now()), "assumptions": {"timezone": timezone_name, "fee_bps": fee_bps, "slippage_bps": slippage_bps, "execution": "next_bar_open", "description": description}}


def demo_equity() -> list[dict[str, Any]]:
    """Illustrative, downsampled test-window paths; endpoints match the cards.

    These are drawing fixtures, not outputs of a market simulator. No claim of
    trading performance is made. Financial results must come from Lane A.
    """
    points: list[dict[str, Any]] = []
    start = datetime(2024, 1, 28, tzinfo=timezone.utc)
    for index in range(45):
        progress = index / 44
        oscillation = math.sin(progress * 6 * math.pi)
        base = 100 * (1 - 0.021 * progress + 0.018 * oscillation)
        rule = 100 * (1 + 0.018 * progress + 0.009 * oscillation)
        proposed = 100 * (1 + 0.046 * progress + 0.006 * oscillation)
        points.append({"date": iso(start + timedelta(hours=round(17 * 24 * progress))), "base": round(base, 4), "rule": round(rule, 4), "proposed": round(proposed, 4), "cash": 100.0})
    return points


def demo_experiment(strategy_id: str, dataset_hash: str, experiment_id: str | None = None) -> dict[str, Any]:
    created = iso(utc_now())
    experiment_id = experiment_id or f"exp_demo_{uuid.uuid4().hex[:12]}"
    regimes = [
        {"id": "regime_01", "trend": "positive", "volatility": "falling", "net_return": 0.084, "trades": 19, "confidence_low": 0.021, "confidence_high": 0.142, "evidence_id": "evidence_regime_01"},
        {"id": "regime_02", "trend": "positive", "volatility": "rising", "net_return": 0.031, "trades": 14, "confidence_low": -0.018, "confidence_high": 0.081, "evidence_id": "evidence_regime_02"},
        {"id": "regime_03", "trend": "sideways", "volatility": "falling", "net_return": -0.012, "trades": 11, "confidence_low": -0.061, "confidence_high": 0.036, "evidence_id": "evidence_regime_03"},
        {"id": "regime_04", "trend": "sideways", "volatility": "rising", "net_return": -0.074, "trades": 17, "confidence_low": -0.136, "confidence_high": -0.011, "evidence_id": "evidence_regime_04"},
        {"id": "regime_05", "trend": "negative", "volatility": "falling", "net_return": -0.026, "trades": 9, "confidence_low": -0.099, "confidence_high": 0.045, "evidence_id": "evidence_regime_05"},
        {"id": "regime_06", "trend": "negative", "volatility": "rising", "net_return": -0.113, "trades": 22, "confidence_low": -0.175, "confidence_high": -0.049, "evidence_id": "evidence_regime_06"},
    ]
    evidence = [
        {"id": "evidence_regime_01", "title": "Trend persistence cluster", "kind": "quantitative", "summary": "The fixture’s positive-trend / falling-volatility cohort has the strongest conditional return, with 19 observations.", "source": "deterministic fixture: regime_performance", "window": "2024-01-01 to 2024-02-14", "facts": [{"label": "Net return", "value": "+8.4%"}, {"label": "Observations", "value": "19"}, {"label": "Interval", "value": "2.1% to 14.2%"}]},
        {"id": "evidence_regime_04", "title": "Volatility switch cost", "kind": "quantitative", "summary": "Sideways and rising-volatility periods are negative after the illustrative switching-cost assumption.", "source": "deterministic fixture: cost_attribution", "window": "2024-01-01 to 2024-02-14", "facts": [{"label": "Net return", "value": "-7.4%"}, {"label": "Switches", "value": "17"}, {"label": "Cost share", "value": "31%"}]},
        {"id": "evidence_holdout", "title": "Unseen-period challenge", "kind": "evaluation", "summary": "The proposed gate is evaluated on a sealed chronological test window in the fixture; values are illustrative until the evaluator is connected.", "source": "deterministic fixture: walk_forward", "window": "test: 2024-01-28 to 2024-02-14", "facts": [{"label": "Policy", "value": "gate-v1"}, {"label": "Access", "value": "sealed"}, {"label": "Status", "value": "illustrative"}]},
    ]
    for regime in regimes:
        if not any(item["id"] == regime["evidence_id"] for item in evidence):
            evidence.append({"id": regime["evidence_id"], "title": f"{regime['trend'].title()} trend / {regime['volatility']} volatility", "kind": "quantitative", "summary": "Illustrative training-cohort evidence. Uncertainty intervals and counts are fixture values.", "source": "deterministic fixture: regime_performance", "window": "training: 2024-01-01 to 2024-01-18", "facts": [{"label": "Net return", "value": f"{regime['net_return']:+.1%}"}, {"label": "Trades", "value": str(regime["trades"])}, {"label": "Interval", "value": f"{regime['confidence_low']:.1%} to {regime['confidence_high']:.1%}"}]})
    for item in evidence:
        if item["id"].startswith("evidence_regime_"):
            item["window"] = "training: 2024-01-01 to 2024-01-18"
    steps = [
        {"id": "step_01", "role": "Diagnostic Analyst", "action": "called_tool", "title": "Mapped conditional performance", "body": "Requested regime_performance and ranked cohorts by after-cost return and sample count.", "status": "complete", "tool": "regime_performance", "evidence_ids": ["evidence_regime_01", "evidence_regime_04"], "timestamp": created},
        {"id": "step_02", "role": "Diagnostic Analyst", "action": "proposed", "title": "Hypothesis: gate rising volatility", "body": "Proposed reducing activation when volatility is rising and trend is sideways or negative.", "status": "complete", "tool": "cost_attribution", "evidence_ids": ["evidence_regime_04", "evidence_regime_06"], "timestamp": created},
        {"id": "step_03", "role": "Independent Critic", "action": "rejected", "title": "Rejected news-causality claim", "body": "No dated news evidence is included in this fixture, so a causal explanation was rejected rather than narrated.", "status": "rejected", "tool": "news_context", "evidence_ids": [], "timestamp": created},
        {"id": "step_04", "role": "Deterministic evaluator", "action": "tested", "title": "Challenged the frozen policy", "body": "A constrained rule gate was frozen before the illustrative test window; the real evaluator is supplied by Part A.", "status": "complete", "tool": "test_gate_train", "evidence_ids": ["evidence_holdout"], "timestamp": created},
        {"id": "step_05", "role": "Independent Critic", "action": "qualified", "title": "Recommendation remains conditional", "body": "The evidence is not sufficient to claim live profitability; use a paper-only test after the real evaluator is connected.", "status": "complete", "tool": "risk_arbiter", "evidence_ids": ["evidence_holdout"], "timestamp": created},
    ]
    return {
        "experiment_id": experiment_id, "strategy_id": strategy_id, "status": "completed", "mode": "demo", "progress": 100,
        "message": "Illustrative fixture complete; replace with Parts A/B measured output before making financial claims.", "created_at": created,
        "policy_id": "gate-v1-illustrative", "dataset_hash": dataset_hash,
        "windows": {"train": "2024-01-01 to 2024-01-18", "validation": "2024-01-19 to 2024-01-27", "test": "2024-01-28 to 2024-02-14"},
        "metrics": [
            {"label": "Base net return", "value": -0.021, "format": "percent", "description": "Illustrative, after assumed costs"},
            {"label": "Proposed gate net return", "value": 0.046, "format": "percent", "description": "Illustrative fixture only"},
            {"label": "Δ vs always-on", "value": 0.067, "format": "percent", "description": "Illustrative difference; not independently measured"},
            {"label": "Switches", "value": 23, "format": "integer", "description": "Illustrative count"},
            {"label": "Holdout coverage", "value": 1.0, "format": "percent", "description": "Fixture coverage"},
        ],
        "baselines": [
            {"id": "always_on", "name": "Always on", "net_return": -0.021, "sharpe": -0.18, "max_drawdown": -0.051989, "exposure": 0.61, "turnover": 1.48, "trades": 92},
            {"id": "cash", "name": "Cash", "net_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "exposure": 0.0, "turnover": 0.0, "trades": 0},
            {"id": "simple_rule", "name": "Fixed trend / vol rule", "net_return": 0.018, "sharpe": 0.22, "max_drawdown": -0.014888, "exposure": 0.43, "turnover": 1.12, "trades": 71},
            {"id": "agent_gate", "name": "Agent-proposed gate", "net_return": 0.046, "sharpe": 0.41, "max_drawdown": -0.005224, "exposure": 0.39, "turnover": 0.96, "trades": 64},
        ],
        "equity": demo_equity(), "regimes": regimes, "evidence": evidence, "steps": steps,
        "hypotheses": [
            {"id": "hyp_01", "title": "Falling volatility supports trend persistence", "status": "supported", "finding": "Supported in the fixture’s conditional cohort; requires measured evaluator confirmation.", "evidence_ids": ["evidence_regime_01"]},
            {"id": "hyp_02", "title": "Rising volatility explains all losses", "status": "inconclusive", "finding": "The cohort is negative but the fixture does not establish causality.", "evidence_ids": ["evidence_regime_04", "evidence_regime_06"]},
            {"id": "hyp_03", "title": "News caused the drawdown", "status": "rejected", "finding": "Rejected because no point-in-time dated news records were available in this run.", "evidence_ids": []},
        ],
        "verdict": "CONDITIONAL", "recommendation": "Illustrative result: activate only under the frozen trend / volatility conditions, then run the measured evaluator and a paper-only champion–challenger test.",
        "limitations": ["All numbers in this demo are deterministic fixture values, not measured market performance.", "The base strategy is not rewritten; only an allocation overlay is illustrated.", "No causal news claim is made.", "No real orders or accounts are connected."],
        "policy": {"description": "Use full exposure in positive trend with falling volatility, half exposure in positive trend with rising volatility, and cash otherwise.", "conditions": ["features must be known by decision time", "next-bar execution", "fees and slippage must be supplied by evaluator", "human approval required before paper test"], "holdout_frozen": True, "test_evaluated": True},
    }


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(min_length=8, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=40)
    strategy_version: str = Field(min_length=1, max_length=100)
    kind: Literal["positions", "trades"]
    mapping: dict[str, str]
    timezone: str = Field(default="UTC", min_length=1, max_length=80)
    fee_bps: float = Field(default=5, ge=0, le=10000)
    slippage_bps: float = Field(default=2, ge=0, le=10000)
    description: str = Field(default="", max_length=1000)

    @field_validator("name", "symbol", "timeframe", "strategy_version", "timezone")
    @classmethod
    def nonblank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy_id: str = Field(min_length=1, max_length=120)


class PaperTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: str = Field(min_length=1, max_length=120)
    duration_days: Literal[14] = 14
    approved: bool


app = FastAPI(title="+EV API", version="0.1.0", description="Part C research workspace API")
app.include_router(team_reports_router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_demo_data()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "research_engine": False, "version": "0.1.0-part-c"}


@app.get("/api/strategies")
def strategies(include_native_example: bool = False) -> list[dict[str, Any]]:
    """List saved strategies, with real native reports opt-in.

    The opt-in keeps the historical collection contract stable for existing
    consumers while allowing the judge flow to request coherent, read-only
    strategy/report pairs.
    """
    values = db_list("strategies")
    if include_native_example:
        existing_ids = {str(item.get("strategy_id")) for item in values}
        for strategy_id in NATIVE_REPORT_STRATEGY_IDS:
            if strategy_id in existing_ids:
                continue
            bundle = native_example_bundle(strategy_id)
            if bundle:
                values.append(bundle["strategy"])
    return values


def native_example_bundle(strategy_id: str | None = None) -> dict[str, Any] | None:
    """Return one virtual report unless a DB record has claimed its IDs."""
    bundle = build_virtual_bundle(strategy_id=strategy_id or DEFAULT_NATIVE_STRATEGY_ID)
    if not bundle:
        return None
    if db_get("strategies", "strategy_id", bundle["strategy"]["strategy_id"]):
        return None
    if db_get("experiments", "experiment_id", bundle["experiment"]["experiment_id"]):
        return None
    return bundle


@app.get("/api/examples/native-report")
def native_report_example(strategy_id: str = DEFAULT_NATIVE_STRATEGY_ID) -> dict[str, Any]:
    """Return one coherent, read-only native report bundle."""
    bundle = native_example_bundle(strategy_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Native report example is unavailable")
    return bundle


def persist_strategy_definition(definition: StrategyDefinitionRequest) -> dict[str, Any]:
    """Persist a validated definition as a draft, without generating signals."""
    strategy_id = f"strat_{uuid.uuid4().hex[:12]}"
    created_at = iso(utc_now())
    definition_dir = DATA_DIR / "definitions"
    definition_dir.mkdir(parents=True, exist_ok=True)
    definition_path = definition_dir / f"{strategy_id}.json"
    definition_path.write_bytes(definition_json_bytes(definition))
    strategy = strategy_record(definition, strategy_id, created_at, str(definition_path))
    db_insert("strategies", strategy_id, strategy)
    return strategy


def _definition_validation_detail(error: ValidationError) -> list[dict[str, Any]]:
    return [
        {"loc": list(item.get("loc", ())), "msg": item.get("msg", "Invalid strategy definition"), "type": item.get("type", "value_error")}
        for item in error.errors()
    ]


def validate_strategy_definition_payload(payload: object) -> StrategyDefinitionRequest:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Strategy definition must be a JSON object")
    try:
        return StrategyDefinitionRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_definition_validation_detail(exc)) from None


@app.post("/api/strategies/definitions")
async def create_strategy_definition(request: Request) -> dict[str, Any]:
    """Save a bounded declarative strategy definition; never execute uploaded text."""
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            if int(declared_length) > MAX_DEFINITION_BYTES:
                raise HTTPException(status_code=413, detail=f"Strategy definition exceeds the {MAX_DEFINITION_BYTES // 1024} KB limit")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header") from None
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_DEFINITION_BYTES:
            raise HTTPException(status_code=413, detail=f"Strategy definition exceeds the {MAX_DEFINITION_BYTES // 1024} KB limit")
        chunks.append(chunk)
    raw = b"".join(chunks)
    if len(raw) > MAX_DEFINITION_BYTES:
        raise HTTPException(status_code=413, detail=f"Strategy definition exceeds the {MAX_DEFINITION_BYTES // 1024} KB limit")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Strategy definition must be valid UTF-8 JSON") from None
    definition = validate_strategy_definition_payload(payload)
    strategy = persist_strategy_definition(definition)
    return {"strategy": strategy, "definition": definition_payload(definition), "definition_hash": strategy["definition_hash"], "valid": True, "issues": []}


@app.get("/api/templates/strategy-definition.json")
def strategy_definition_template() -> Response:
    definition = template_definition()
    return Response(
        content=definition_json_bytes(definition),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=strategy-definition.json"},
    )


@app.get("/api/strategies/{strategy_id}/definition")
def download_strategy_definition(strategy_id: str) -> Response:
    strategy = db_get("strategies", "strategy_id", strategy_id)
    if not strategy or strategy.get("source") != "strategy_definition" or not isinstance(strategy.get("definition"), dict):
        raise HTTPException(status_code=404, detail="Strategy definition not found")
    filename = re.sub(r"[^A-Za-z0-9_.-]", "_", strategy_id)
    content = json.dumps(strategy["definition"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}-definition.json"},
    )


@app.post("/api/imports/preview")
def preview(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = safe_filename(file.filename or "upload.csv")
    # Read the bounded spooled upload directly. This keeps the small preview
    # path deterministic in local workers and avoids a threadpool dependency.
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    columns, rows, row_count, problems = read_upload(content, filename)
    mapping, detected_kind = suggest_mapping(columns)
    if columns:
        aliases = POSITION_ALIASES if detected_kind == "positions" else TRADE_ALIASES
        missing = [field for field in aliases if field not in mapping]
        if missing:
            problems.append(issue("warning", "mapping_needed", f"Map these fields before import: {', '.join(missing)}"))
    upload_id = f"upl_{uuid.uuid4().hex[:14]}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = UPLOAD_DIR / f"{upload_id}_{filename}"
    raw_path.write_bytes(content)
    payload = {"upload_id": upload_id, "filename": filename, "columns": columns, "rows": rows, "row_count": row_count, "suggested_mapping": mapping, "detected_kind": detected_kind, "issues": problems, "raw_path": str(raw_path), "created_at": iso(utc_now())}
    db_insert("uploads", upload_id, payload)
    return {key: payload[key] for key in ("upload_id", "filename", "columns", "rows", "row_count", "suggested_mapping", "detected_kind", "issues")}


@app.post("/api/strategies/import")
def import_strategy(request: ImportRequest) -> dict[str, Any]:
    upload = db_get("uploads", "upload_id", request.upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload preview not found or expired")
    raw_path = Path(upload["raw_path"])
    if not raw_path.exists():
        raise HTTPException(status_code=410, detail="Uploaded file is no longer available")
    content = raw_path.read_bytes()
    columns, _, row_count, read_problems = read_upload(content, upload["filename"])
    suffix = raw_path.suffix.lower()
    if any(item["severity"] == "error" for item in read_problems):
        return {"strategy": None, "issues": read_problems, "valid": False}
    if suffix in {".parquet", ".pq"}:
        try:
            import pyarrow.parquet as parquet  # type: ignore
            rows = [json_safe(row) for row in parquet.read_table(io.BytesIO(content)).to_pylist()]
        except Exception as exc:
            rows = []
            read_problems.append(issue("error", "parquet_read_error", f"Could not read Parquet: {exc}"))
    else:
        try:
            reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
            reader.fieldnames = [name.strip() for name in (reader.fieldnames or [])]
            rows = [{str(key): (value if value != "" else None) for key, value in row.items() if key is not None} for row in reader]
        except Exception as exc:
            rows = []
            read_problems.append(issue("error", "csv_parse_error", f"Could not read CSV: {exc}"))
    normalized, problems, date_start, date_end = validate_rows(columns, rows, request.kind, request.mapping, request.timezone)
    problems = read_problems + problems
    if any(item["severity"] == "error" for item in problems):
        return {"strategy": None, "issues": problems, "valid": False}
    expected_symbol = request.symbol.strip().upper()
    row_symbols = {str(item["symbol"]).upper() for item in normalized}
    if row_symbols != {expected_symbol}:
        return {"strategy": None, "issues": problems + [issue("error", "symbol_mismatch", f"Metadata symbol {expected_symbol} does not match data symbols: {', '.join(sorted(row_symbols))}")], "valid": False}
    dataset_hash = hashlib.sha256(content).hexdigest()
    strategy_id = f"strat_{uuid.uuid4().hex[:12]}"
    status = "ready" if request.kind == "positions" else "diagnosis_only"
    strategy = strategy_payload(strategy_id, request.name, request.symbol.upper(), request.timeframe, request.strategy_version, "user_upload", request.kind, status, len(normalized), date_start or "", date_end or "", dataset_hash, request.timezone, request.fee_bps, request.slippage_bps, request.description)
    canonical_bytes = dumps(normalized).encode("utf-8")
    canonical_path = DATA_DIR / "canonical" / f"{strategy_id}.json"
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_bytes(canonical_bytes)
    strategy.update({"source_kind": "csv" if suffix == ".csv" else "parquet", "source_upload_id": request.upload_id, "source_filename": upload["filename"], "source_mapping": request.mapping, "raw_path": str(raw_path), "raw_data_hash": dataset_hash, "canonical_data_path": str(canonical_path), "canonical_data_hash": hashlib.sha256(canonical_bytes).hexdigest()})
    db_insert("strategies", strategy_id, strategy)
    return {"strategy": strategy, "issues": problems, "valid": True}


@app.get("/api/templates/positions.csv")
def positions_template() -> Response:
    body = "decision_time,symbol,target_position\n2024-01-01T00:00:00Z,BTCUSDT,0\n2024-01-01T01:00:00Z,BTCUSDT,1\n"
    return Response(content=body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=positions.csv"})


@app.get("/api/templates/trades.csv")
def trades_template() -> Response:
    body = "entry_time,exit_time,symbol,side,quantity,entry_price,exit_price\n2024-01-01T01:00:00Z,2024-01-01T04:00:00Z,BTCUSDT,long,1,42000,42500\n"
    return Response(content=body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=trades.csv"})


@app.get("/api/experiments")
def experiments(strategy_id: str | None = None, include_native_example: bool = False) -> list[dict[str, Any]]:
    values = db_list("experiments", "created_at DESC")
    if strategy_id in NATIVE_REPORT_STRATEGY_IDS:
        if any(item.get("strategy_id") == strategy_id for item in values):
            return [item for item in values if item.get("strategy_id") == strategy_id]
        bundle = native_example_bundle(strategy_id)
        return [bundle["experiment"]] if bundle else []
    if include_native_example:
        existing_ids = {str(item.get("experiment_id")) for item in values}
        for native_strategy_id in NATIVE_REPORT_STRATEGY_IDS:
            bundle = native_example_bundle(native_strategy_id)
            if bundle and bundle["experiment"]["experiment_id"] not in existing_ids:
                values.append(bundle["experiment"])
    return [item for item in values if strategy_id is None or item["strategy_id"] == strategy_id]


@app.post("/api/experiments")
def create_experiment(request: ExperimentRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    strategy = db_get("strategies", "strategy_id", request.strategy_id)
    if not strategy:
        if is_virtual_strategy(request.strategy_id):
            bundle = native_example_bundle(request.strategy_id)
            if bundle:
                return bundle["experiment"]
        raise HTTPException(status_code=404, detail="Strategy not found")
    experiment_id = f"exp_{uuid.uuid4().hex[:14]}"
    if strategy["status"] == "demo":
        experiment = {"experiment_id": experiment_id, "strategy_id": strategy["strategy_id"], "status": "queued", "mode": "demo", "progress": 0, "message": "Research replay queued; the stored fixture will be replaced by Part A/B measured output when connected.", "created_at": iso(utc_now()), "policy_id": "pending", "dataset_hash": strategy["dataset_hash"], "windows": {"train": "pending", "validation": "pending", "test": "pending"}, "metrics": [], "baselines": [], "equity": [], "regimes": [], "evidence": [], "steps": [], "hypotheses": [], "verdict": "INCONCLUSIVE", "recommendation": "Research replay queued.", "limitations": ["This run begins from a deterministic demo fixture.", "No real trading or brokerage connection is involved."], "policy": {"description": "Pending research replay", "conditions": [], "holdout_frozen": False, "test_evaluated": False}}
        db_insert("experiments", experiment_id, experiment)
        if background_tasks is None:
            run_demo_experiment(experiment_id, strategy["strategy_id"], strategy["dataset_hash"])
            return db_get("experiments", "experiment_id", experiment_id) or experiment
        background_tasks.add_task(run_demo_experiment, experiment_id, strategy["strategy_id"], strategy["dataset_hash"])
        return experiment
    else:
        now = iso(utc_now())
        experiment = {"experiment_id": experiment_id, "strategy_id": strategy["strategy_id"], "status": "awaiting_engine", "mode": "pending", "progress": 0, "message": "Imported strategy validated and queued. Parts A/B must supply the point-in-time evaluator before metrics or agent findings can be shown.", "created_at": now, "policy_id": "pending", "dataset_hash": strategy["dataset_hash"], "windows": {"train": "pending", "validation": "pending", "test": "pending"}, "metrics": [], "baselines": [], "equity": [], "regimes": [], "evidence": [], "steps": [], "hypotheses": [], "verdict": "INCONCLUSIVE", "recommendation": "Awaiting the deterministic research engine. No illustrative metrics have been assigned to this upload.", "limitations": ["Parts A/B evaluator is not connected.", "No financial performance claim is made.", "Trade-only imports support diagnosis but not faithful alternate gate simulation."], "policy": {"description": "Pending evaluator", "conditions": [], "holdout_frozen": False, "test_evaluated": False}}
    db_insert("experiments", experiment_id, experiment)
    return experiment


def run_demo_experiment(experiment_id: str, strategy_id: str, dataset_hash: str) -> None:
    """Replay the checked-in fixture; replace this worker with Part A/B orchestration."""
    queued = db_get("experiments", "experiment_id", experiment_id)
    if queued:
        queued["status"] = "running"
        queued["progress"] = 35
        queued["message"] = "Fixture research replay running; all values remain illustrative."
        db_insert("experiments", experiment_id, queued)
    completed = demo_experiment(strategy_id, dataset_hash, experiment_id)
    db_insert("experiments", experiment_id, completed)


@app.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id: str) -> dict[str, Any]:
    value = db_get("experiments", "experiment_id", experiment_id)
    if not value and is_virtual_experiment(experiment_id):
        bundle = native_example_bundle(strategy_id_for_experiment(experiment_id))
        if bundle:
            return bundle["experiment"]
    if not value:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return value


@app.get("/api/experiments/{experiment_id}/report")
def report(experiment_id: str) -> Response:
    value = db_get("experiments", "experiment_id", experiment_id)
    if not value and is_virtual_experiment(experiment_id):
        bundle = native_example_bundle(strategy_id_for_experiment(experiment_id))
        if bundle:
            value = bundle["experiment"]
    if not value:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return Response(content=json.dumps(value, indent=2, ensure_ascii=False), media_type="application/json", headers={"Content-Disposition": f"attachment; filename={experiment_id}-report.json"})


@app.post("/api/paper-tests")
def create_paper_test(request: PaperTestRequest) -> dict[str, Any]:
    if not request.approved:
        raise HTTPException(status_code=400, detail="Human approval is required before freezing a paper test")
    experiment = db_get("experiments", "experiment_id", request.experiment_id)
    if not experiment and is_virtual_experiment(request.experiment_id):
        bundle = native_example_bundle(strategy_id_for_experiment(request.experiment_id))
        if bundle:
            experiment = bundle["experiment"]
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if experiment.get("paper_eligible") is False:
        raise HTTPException(status_code=409, detail="This recorded report has no eligible paper proposal; a sealed score is not an approved candidate verdict")
    if experiment["status"] != "completed" or not experiment.get("policy", {}).get("test_evaluated") or not experiment.get("policy", {}).get("holdout_frozen"):
        raise HTTPException(status_code=409, detail="Only a completed, evaluated experiment can be frozen")
    paper_id = f"paper_{uuid.uuid4().hex[:14]}"
    strategy = db_get("strategies", "strategy_id", experiment["strategy_id"])
    plan = {"paper_test_id": paper_id, "experiment_id": experiment["experiment_id"], "status": "planned", "duration_days": 14, "approved_at": iso(utc_now()), "policy_id": experiment["policy_id"], "mode": experiment["mode"], "execution": "paper_only", "message": "Frozen plan recorded. No trading or brokerage connection was started.", "snapshot": {"strategy_id": experiment["strategy_id"], "dataset_hash": experiment["dataset_hash"], "policy_id": experiment["policy_id"], "windows": experiment["windows"], "policy": experiment["policy"], "assumptions": strategy.get("assumptions", {}) if strategy else {}}}
    db_insert("paper_tests", paper_id, plan)
    return plan


@app.get("/api/paper-tests")
def paper_tests() -> list[dict[str, Any]]:
    return db_list("paper_tests", "approved_at DESC")


def seed_demo_data() -> None:
    existing = db_get("strategies", "strategy_id", "demo_btc_trend_v1")
    if existing and existing.get("strategy_version") == "fixture-v2":
        return
    common = {
        "symbol": "BTCUSDT", "timeframe": "1h", "version": "fixture-v2", "source": "demo_fixture",
        "kind": "positions", "status": "demo", "row_count": 1057,
        "date_start": "2024-01-01T00:00:00Z", "date_end": "2024-02-14T00:00:00Z",
        "timezone_name": "UTC", "fee_bps": 5, "slippage_bps": 2,
        "description": "Deterministic research fixture. Illustrative only; not a live or independently validated strategy.",
    }
    first = strategy_payload(strategy_id="demo_btc_trend_v1", name="BTC Trend Following", dataset_hash="sha256:fixture-btc-trend-v1", **common)
    second = strategy_payload(strategy_id="demo_btc_mean_reversion_v1", name="BTC Mean Reversion", dataset_hash="sha256:fixture-btc-mean-reversion-v1", description="Deterministic second fixture used to demonstrate strategy selection. Illustrative only; not a live or independently validated strategy.", **{key: value for key, value in common.items() if key != "description"})
    db_insert("strategies", first["strategy_id"], first)
    db_insert("strategies", second["strategy_id"], second)
    experiment = demo_experiment(first["strategy_id"], first["dataset_hash"], "exp_demo_btc_trend")
    db_insert("experiments", experiment["experiment_id"], experiment)
    second_experiment = demo_experiment(second["strategy_id"], second["dataset_hash"], "exp_demo_btc_mean_reversion")
    second_experiment["recommendation"] = "Illustrative result: monitor the mean-reversion fixture until the measured evaluator confirms that regime selection survives after costs."
    second_experiment["verdict"] = "MONITOR"
    db_insert("experiments", second_experiment["experiment_id"], second_experiment)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.main:app", host="127.0.0.1", port=8000, reload=False)
