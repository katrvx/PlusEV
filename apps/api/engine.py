"""Score an imported position file with Lane A, then Lane B.

Demo fixtures never come through here. Trade logs and anything other than
BTCUSDT 1h stay pending: this snapshot cannot price them. Financial numbers
are computed by Lane A. The dict returned here is only the Part C presentation.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ENGINE_CONNECTED = True
SNAPSHOT_ID = "binance-spot-btcusdt-1h-202411-202610"
HOURLY = {"1h", "1hr", "1hour", "60m", "60min", "hourly"}
VERDICT_FOR_UI = {
    "KEEP": "KEEP",
    "KILL": "KILL",
    "MONITOR": "MONITOR",
    "INCONCLUSIVE": "INCONCLUSIVE",
    "ACTIVATE CONDITIONALLY": "CONDITIONAL",
    "REDUCE": "REDUCE",
}
POLICY_NAMES = {
    "always_on": "Original strategy",
    "cash": "Cash",
    "simple_rule": "Simple trend / vol rule",
    "lgbm_gate": "LightGBM gate",
    "agent_gate": "Suggested rule",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_import_path() -> None:
    root = _repo_root()
    for path in (root, root / "A"):
        entry = str(path)
        if entry not in sys.path:
            sys.path.insert(0, entry)


def refusal_reason(strategy: dict[str, Any]) -> str | None:
    """Why this import cannot be scored. None means the worker should run."""

    if strategy.get("kind") != "positions" or strategy.get("status") != "ready":
        return (
            "A trade log can be stored for diagnosis. It has no target position at each "
            "decision time, so an alternate gate cannot be simulated. No metrics were assigned."
        )
    symbol = str(strategy.get("symbol", "")).upper()
    timeframe = str(strategy.get("timeframe", "")).strip().lower().replace(" ", "")
    if symbol != "BTCUSDT" or timeframe not in HOURLY:
        return (
            "The connected evaluator only scores BTCUSDT hourly positions against the Binance "
            "spot snapshot from 2024-11-01 through 2026-10-31. This import is stored and waiting. "
            "No metrics were assigned."
        )
    return None


def run_measured_experiment(
    experiment_id: str,
    strategy: dict[str, Any],
    *,
    n_boot: int = 200,
    n_estimators: int = 120,
    force_fallback: bool | None = None,
) -> dict[str, Any]:
    """Run Lane A and Lane B, then persist the presentation record and the investigation JSON."""

    from apps.api.main import db_get, db_insert

    current = db_get("experiments", "experiment_id", experiment_id) or {}
    current.update(
        {
            "status": "running",
            "progress": 35,
            "message": "Scoring the imported positions on the Binance spot snapshot. The sealed test stays closed to the agents.",
        }
    )
    db_insert("experiments", experiment_id, current)
    try:
        payload = measure(
            experiment_id,
            strategy,
            n_boot=n_boot,
            n_estimators=n_estimators,
            force_fallback=force_fallback,
        )
    except Exception as exc:
        payload = _failed(experiment_id, strategy, exc)
    db_insert("experiments", experiment_id, payload)
    return payload


def measure(
    experiment_id: str,
    strategy: dict[str, Any],
    *,
    n_boot: int = 200,
    n_estimators: int = 120,
    force_fallback: bool | None = None,
) -> dict[str, Any]:
    _ensure_import_path()
    from kok_a.experiment import agent_view, assemble, score_frozen
    from kok_a.gates import allocation
    from kok_a.simulate import simulate
    from packages.research_agents.investigate import investigate

    positions = _load_positions(strategy)
    assumptions = strategy.get("assumptions") or {}
    fee = float(assumptions.get("fee_bps", 10))
    slip = float(assumptions.get("slippage_bps", 1))
    bundle = assemble(
        str(strategy["strategy_id"]),
        SNAPSHOT_ID,
        n_boot=n_boot,
        n_estimators=n_estimators,
        external_positions=positions,
        fee_bps=fee,
        slippage_bps=slip,
    )
    view = agent_view(bundle.result).model_copy(
        update={"experiment_id": experiment_id, "strategy_id": str(strategy["strategy_id"])}
    )
    use_fallback = force_fallback if force_fallback is not None else not os.environ.get("KOK_AGENT_MODEL")
    report = None
    agent_note = None
    try:
        report = investigate(
            experiment_id,
            loader=lambda _experiment_id: (view, bundle.runner, bundle.quantiles, None, bundle.lgbm),
            force_fallback=use_fallback,
        )
        _write_report(report)
    except Exception as exc:
        agent_note = f"Lane B investigation did not finish ({type(exc).__name__}: {exc}). Lane A numbers below are still from the pre-registered comparison."

    champion = _champion_evaluation(report, bundle.runner, score_frozen) if report is not None else None
    return _present(experiment_id, strategy, bundle, report, champion, allocation, simulate, agent_note)


def _load_positions(strategy: dict[str, Any]) -> pd.DataFrame:
    path = Path(str(strategy.get("canonical_data_path", "")))
    if not path.is_file():
        raise RuntimeError("The imported position file is no longer on disk, so it was not scored.")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("The imported position file has no rows, so it was not scored.")
    frame = pd.DataFrame(rows)
    missing = {"decision_time", "target_position"} - set(frame.columns)
    if missing:
        raise RuntimeError(f"Imported positions are missing {', '.join(sorted(missing))}.")
    return frame


def _champion_evaluation(report: Any, runner: Any, score_frozen: Any) -> Any | None:
    champion_id = getattr(report, "champion_policy_id", None)
    if not champion_id:
        return None
    spec = next(
        (
            candidate.policy_spec
            for candidate in report.candidates
            if candidate.policy_id == champion_id and candidate.status == "accepted_for_frozen_test"
        ),
        None,
    )
    if spec is None:
        return None
    return score_frozen(runner, [spec])[0]


def _write_report(report: Any) -> None:
    from apps.api import team_reports

    directory = team_reports.ROOT / "experiments"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"investigation_{report.experiment_id}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def _present(
    experiment_id: str,
    strategy: dict[str, Any],
    bundle: Any,
    report: Any,
    champion: Any,
    allocation: Any,
    simulate: Any,
    agent_note: str | None,
) -> dict[str, Any]:
    result = bundle.result
    decision = result.decision
    if decision is None:
        raise RuntimeError("Lane A returned no verdict.")
    curves = _curves(bundle, allocation, simulate)
    selected = _short_policy(decision.policy_id, bundle)
    proposed = curves.get(selected, curves["cash"])
    verdict = VERDICT_FOR_UI.get(decision.verdict, decision.verdict)
    tested = decision.verdict != "INCONCLUSIVE"
    limitations = list(result.notes)
    limitations.append(
        f"The suggested line on the chart is {POLICY_NAMES.get(selected, selected)}, "
        "the deterministic arbiter's selection. It is not a claim that an agent discovered it."
    )
    if champion is None:
        limitations.append("No agent gate met the pre-registered rule, so none was shown the sealed test.")
    else:
        limitations.append(
            f"Agent champion {champion.policy_id} was scored once on the sealed test and is in the comparison table."
        )
    if agent_note:
        limitations.append(agent_note)
    limitations.append("Historical simulation only. No brokerage connection and no order was sent.")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    windows = {window.split: f"{window.start.date().isoformat()} to {window.end.date().isoformat()}" for window in result.windows}
    return {
        "experiment_id": experiment_id,
        "strategy_id": strategy["strategy_id"],
        "status": "completed",
        "mode": "measured",
        "progress": 100,
        "message": "Measured on the Binance spot BTCUSDT 1h snapshot. Demo fixtures were not used.",
        "created_at": now,
        "policy_id": selected,
        "dataset_hash": strategy.get("dataset_hash", ""),
        "windows": {"train": windows.get("train", "pending"), "validation": windows.get("validation", "pending"), "test": windows.get("test", "pending")},
        "metrics": _metrics(result, selected, champion),
        "baselines": _baselines(result, champion),
        "equity": _equity_points(bundle.frame, curves, proposed),
        "regimes": _regimes(bundle, curves["always_on_sim"]),
        "evidence": _evidence(report),
        "steps": _steps(report, now),
        "hypotheses": _hypotheses(report),
        "verdict": verdict,
        "recommendation": _recommendation(decision, report),
        "limitations": limitations,
        "policy": {
            "description": _policy_description(decision, bundle.runner),
            "conditions": [
                "features must be known by decision time",
                "next-bar open fill",
                f"assumed cost {float((strategy.get('assumptions') or {}).get('fee_bps', 10)):.0f} bps fee + {float((strategy.get('assumptions') or {}).get('slippage_bps', 1)):.0f} bp slippage",
                "human approval required before a paper test",
            ],
            "holdout_frozen": True,
            "test_evaluated": tested,
        },
    }


def _short_policy(policy_id: str, bundle: Any) -> str:
    if policy_id in {"always_on", "cash", "simple_rule", "lgbm_gate"}:
        return policy_id
    rule = getattr(bundle.runner, "rule_spec", None) or {}
    if policy_id == rule.get("policy_id"):
        return "simple_rule"
    if policy_id == bundle.lgbm.spec().get("policy_id"):
        return "lgbm_gate"
    return policy_id


def _curves(bundle: Any, allocation: Any, simulate: Any) -> dict[str, Any]:
    frame = bundle.frame
    runner = bundle.runner
    specs = {
        "always_on": {"policy_id": "always_on", "family": "always_on"},
        "cash": {"policy_id": "cash", "family": "cash"},
        "simple_rule": runner.rule_spec,
        "lgbm_gate": bundle.lgbm.spec(),
    }
    curves: dict[str, Any] = {}
    for name, spec in specs.items():
        multiplier = allocation(spec, frame, lgbm=runner.lgbm)
        sim = simulate(frame, multiplier, fee_bps=runner.fee_bps, slippage_bps=runner.slippage_bps)
        curves[name] = (1.0 + sim["net"].to_numpy(dtype=float)).cumprod() * 100.0
        if name == "always_on":
            curves["always_on_sim"] = sim
    return curves


def _equity_points(frame: pd.DataFrame, curves: dict[str, Any], proposed: Any) -> list[dict[str, Any]]:
    count = len(frame)
    step = max(1, count // 1500)
    indexes = list(range(0, count, step))
    if indexes[-1] != count - 1:
        indexes.append(count - 1)
    points = []
    for index in indexes:
        points.append(
            {
                "date": _iso(frame["decision_time"].iloc[index]),
                "base": round(float(curves["always_on"][index]), 4),
                "rule": round(float(curves["simple_rule"][index]), 4),
                "proposed": round(float(proposed[index]), 4),
                "cash": round(float(curves["cash"][index]), 4),
            }
        )
    return points


def _metrics(result: Any, selected: str, champion: Any) -> list[dict[str, Any]]:
    by_policy = {row.policy: row.metrics for row in result.baselines if row.split == "test"}
    base = by_policy["always_on"]
    chosen = by_policy.get(selected, base)
    rows = [
        {"label": "Base net return", "value": base.net_return, "format": "percent", "description": "Unchanged strategy, sealed test, after the assumed cost"},
        {"label": f"{POLICY_NAMES.get(selected, selected)} net return", "value": chosen.net_return, "format": "percent", "description": "Arbiter selection on the sealed test"},
        {"label": "Δ vs always-on", "value": chosen.net_return - base.net_return, "format": "percent", "description": "Difference of compounded test returns"},
        {"label": "Switches", "value": chosen.n_switches, "format": "integer", "description": "Position changes of the selected overlay on the test window"},
    ]
    if champion is not None:
        rows.append(
            {
                "label": "Agent champion net return",
                "value": champion.metrics.net_return,
                "format": "percent",
                "description": "One sealed-test look. Not a second chance to change the rule.",
            }
        )
    return rows


def _baselines(result: Any, champion: Any) -> list[dict[str, Any]]:
    rows = []
    for row in result.baselines:
        if row.split != "test":
            continue
        metrics = row.metrics
        rows.append(_baseline(row.policy, POLICY_NAMES.get(row.policy, row.policy), metrics))
    if champion is not None:
        rows.append(_baseline("agent_gate", "Agent champion", champion.metrics))
    return rows


def _baseline(policy_id: str, name: str, metrics: Any) -> dict[str, Any]:
    sharpe = metrics.sharpe
    return {
        "id": policy_id,
        "name": name,
        "net_return": float(metrics.net_return),
        "sharpe": 0.0 if sharpe is None else float(sharpe),
        "max_drawdown": -abs(float(metrics.max_drawdown)),
        "exposure": float(metrics.exposure),
        "turnover": float(metrics.turnover),
        "trades": int(metrics.n_switches),
    }


def _regimes(bundle: Any, always_sim: pd.DataFrame) -> list[dict[str, Any]]:
    frame = bundle.frame
    train = frame["split"] == "train"
    cards = []
    for feature in ("trend_regime", "vol_regime"):
        grouped = frame.loc[train].groupby(feature, sort=True)
        for bucket, part in grouped:
            net = always_sim.loc[part.index, "net"].to_numpy(dtype=float)
            if len(net) == 0 or not pd.notna(net).all():
                continue
            compounded = float((1.0 + net).prod() - 1.0)
            trades = int((always_sim.loc[part.index, "dq_signed"] > 1e-12).sum())
            cards.append(
                {
                    "id": f"train-{feature}-{bucket}",
                    "trend": str(bucket) if feature == "trend_regime" else "all",
                    "volatility": str(bucket) if feature == "vol_regime" else "all",
                    "net_return": compounded,
                    "trades": trades,
                    "confidence_low": compounded,
                    "confidence_high": compounded,
                    "evidence_id": f"train-{feature}-{bucket}",
                }
            )
    return cards


def _evidence(report: Any) -> list[dict[str, Any]]:
    if report is None:
        return []
    cited = {evidence_id for hypothesis in report.diagnostic.hypotheses for evidence_id in hypothesis.evidence_ids}
    chosen = [item for item in report.evidence if item.evidence_id in cited] or list(report.evidence[:8])
    cards = []
    for item in chosen:
        cards.append(
            {
                "id": item.evidence_id,
                "title": item.tool,
                "kind": "research",
                "summary": "Recorded tool output. The investigation report keeps the full payload.",
                "source": "lane_b",
                "window": "development splits only",
                "facts": [{"label": "Tool", "value": item.tool}],
            }
        )
    return cards


def _steps(report: Any, now: str) -> list[dict[str, Any]]:
    if report is None:
        return []
    summary = report.diagnostic.summary
    cited = {evidence_id for hypothesis in report.diagnostic.hypotheses for evidence_id in hypothesis.evidence_ids}
    evidence_ids = [item.evidence_id for item in report.evidence if item.evidence_id in cited][:4]
    if not evidence_ids:
        evidence_ids = [item.evidence_id for item in report.evidence[:4]]
    steps = [
        {
            "id": "step_diagnose",
            "role": "Diagnostic Analyst",
            "action": "called_tool",
            "title": "Read the training regimes",
            "body": summary,
            "status": "complete",
            "tool": "regime_performance",
            "evidence_ids": evidence_ids[:2],
            "timestamp": now,
        },
        {
            "id": "step_propose",
            "role": "Gate proposer",
            "action": "proposed",
            "title": "Proposed allowlisted gates" if report.proposals else "No testable gate proposal",
            "body": f"{len(report.proposals)} proposal(s) on train. Validation is reserved for the arbiter.",
            "status": "complete",
            "tool": "test_gate_train",
            "evidence_ids": evidence_ids[2:4] or evidence_ids[:1],
            "timestamp": now,
        },
        {
            "id": "step_arbitrate",
            "role": "Deterministic arbiter",
            "action": "tested",
            "title": "Selected at most one agent champion",
            "body": report.verdict if isinstance(report.verdict, str) else "Investigation finished.",
            "status": "complete",
            "tool": "arbiter_evaluate",
            "evidence_ids": evidence_ids[:1],
            "timestamp": now,
        },
    ]
    return steps


def _hypotheses(report: Any) -> list[dict[str, Any]]:
    if report is None:
        return []
    cards = []
    for hypothesis in report.diagnostic.hypotheses:
        cards.append(
            {
                "id": hypothesis.hypothesis_id,
                "title": hypothesis.statement[:140],
                "status": "inconclusive",
                "finding": hypothesis.statement + " Train association only; not a holdout confirmation.",
                "evidence_ids": list(hypothesis.evidence_ids),
            }
        )
    return cards


def _recommendation(decision: Any, report: Any) -> str:
    text = f"{decision.verdict}. " + " ".join(decision.reasons)
    if report is not None and report.champion_policy_id:
        text += f" Agent layer champion: {report.champion_policy_id}, scored once."
    elif report is not None:
        text += " The agent layer added no champion."
    return text


def _policy_description(decision: Any, runner: Any) -> str:
    rule = getattr(runner, "rule_spec", None) or {}
    if decision.policy_id == "simple_rule" and rule:
        false_alloc = rule.get("allocation_when_false")
        return (
            "Full size only when 24h momentum is positive and 7d volatility is at or below the train median; "
            f"otherwise allocation {false_alloc}."
        )
    return f"Arbiter selection: {decision.policy_id}. The uploaded strategy is unchanged; only the allocation overlay moves."


def _failed(experiment_id: str, strategy: dict[str, Any], exc: Exception) -> dict[str, Any]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    message = str(exc).strip() or type(exc).__name__
    return {
        "experiment_id": experiment_id,
        "strategy_id": strategy["strategy_id"],
        "status": "failed",
        "mode": "pending",
        "progress": 100,
        "message": message,
        "created_at": now,
        "policy_id": "pending",
        "dataset_hash": strategy.get("dataset_hash", ""),
        "windows": {"train": "pending", "validation": "pending", "test": "pending"},
        "metrics": [],
        "baselines": [],
        "equity": [],
        "regimes": [],
        "evidence": [],
        "steps": [],
        "hypotheses": [],
        "verdict": "INCONCLUSIVE",
        "recommendation": message,
        "limitations": [message, "No demo fixture numbers were attached to this upload."],
        "policy": {"description": "Not scored", "conditions": [], "holdout_frozen": False, "test_evaluated": False},
    }


def _iso(value: Any) -> str:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
