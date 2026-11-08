"""Read-only Argon-report adapters for the judge workflow.

These checked-in native artifacts are useful for showing a coherent evidence
trace, but they do not authorize a new evaluation.  This module adapts them
into the Part C presentation shapes without creating a database record or
inventing market data, dates, costs, metrics, charts, or paper-test eligibility.

The adapter is deliberately opt-in from the collection endpoints.  Existing
API consumers continue to receive the two seeded demo strategies, while the
web judge flow can request this one coherent example and keep its native
strategy_id/experiment_id identity intact.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from . import team_reports


# ---------------------------------------------------------------------------
# Real Argon report adapters
# ---------------------------------------------------------------------------
#
# The adapter stays in one module so the existing route namespace can expose
# real reports without migrating every caller at once.

_ROOT = Path(__file__).resolve().parents[2]
NATIVE_REPORTS: dict[str, dict[str, str]] = {
    "btc-trend-24-72-demo": {
        "experiment_id": "exp_dea9445d0576",
        "name": "BTC trend · 24–72h",
        "timeframe": "24–72h",
        "report_path": "experiments/investigation_argon_lane_a.json",
    },
    "btc-meanrev-48-demo": {
        "experiment_id": "exp_a79497cf70ec",
        "name": "BTC mean reversion · 48h",
        "timeframe": "48h",
        "report_path": "experiments/investigation_argon_meanrev.json",
        "frozen_path": "experiments/frozen_look_btc-meanrev-48-demo.json",
    },
}
NATIVE_REPORT_STRATEGY_IDS = tuple(NATIVE_REPORTS)
DEFAULT_NATIVE_STRATEGY_ID = "btc-meanrev-48-demo"
NATIVE_EXAMPLE_EXPERIMENT_ID = NATIVE_REPORTS[DEFAULT_NATIVE_STRATEGY_ID]["experiment_id"]
NATIVE_EXAMPLE_STRATEGY_ID = DEFAULT_NATIVE_STRATEGY_ID


def _spec_for_strategy(strategy_id: str | None) -> tuple[str, dict[str, str]] | None:
    selected = strategy_id or DEFAULT_NATIVE_STRATEGY_ID
    spec = NATIVE_REPORTS.get(selected)
    return (selected, spec) if spec is not None else None


def _native_wrapper(strategy_id: str | None = None) -> dict[str, Any] | None:
    """Load one non-synthetic report through the trusted report API."""
    selected = _spec_for_strategy(strategy_id)
    if selected is None:
        return None
    selected_id, spec = selected
    try:
        wrapper = team_reports.get_investigation(spec["experiment_id"])
    except HTTPException:
        return None
    report = wrapper.get("report")
    # Refuse the old checked-in fixture even if a future artifact reuses an ID.
    if wrapper.get("synthetic") is not False or wrapper.get("source") != "team_artifact":
        return None
    if not isinstance(report, dict):
        return None
    if report.get("experiment_id") != spec["experiment_id"] or report.get("strategy_id") != selected_id:
        return None
    return wrapper


def _load_frozen_look(strategy_id: str, spec: dict[str, str]) -> dict[str, Any] | None:
    path_value = spec.get("frozen_path")
    if not path_value:
        return None
    try:
        raw = json.loads((_ROOT / path_value).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    if raw.get("strategy_id") != strategy_id or raw.get("experiment_id") != spec["experiment_id"]:
        return None
    return raw if isinstance(raw.get("evaluation"), dict) else None


def _resolve_wrapper(
    wrapper: dict[str, Any] | None = None,
    strategy_id: str | None = None,
) -> tuple[str, dict[str, str], dict[str, Any]] | None:
    selected = _spec_for_strategy(strategy_id)
    if selected is None:
        return None
    selected_id, spec = selected
    resolved = wrapper or _native_wrapper(selected_id)
    if not resolved or not isinstance(resolved.get("report"), dict):
        return None
    report = resolved["report"]
    if report.get("strategy_id") != selected_id or report.get("experiment_id") != spec["experiment_id"]:
        return None
    return selected_id, spec, resolved


def _evidence_label(tool: str) -> str:
    return {
        "regime_performance": "Market-condition check",
        "cost_attribution": "Cost attribution check",
        "feature_grid": "Feature coverage check",
        "test_gate_train": "Candidate rule check",
        "arbiter_evaluate": "Independent policy review",
        "score_frozen": "Frozen-look evaluation",
    }.get(tool, "Recorded source check")


def _evidence_summary(evidence: dict[str, Any], source_path: str) -> dict[str, Any]:
    evidence_id = str(evidence.get("evidence_id") or "")
    tool = str(evidence.get("tool") or "research check")
    args = evidence.get("args") if isinstance(evidence.get("args"), dict) else {}
    payload = evidence.get("payload") if isinstance(evidence.get("payload"), dict) else {}
    split = payload.get("split") or args.get("split")
    facts = [
        {"label": "Evidence ID", "value": evidence_id},
        {"label": "Recorded check", "value": _evidence_label(tool)},
    ]
    if isinstance(split, str) and split:
        facts.append({"label": "Research stage", "value": split})
    note = payload.get("note") if isinstance(payload.get("note"), str) else ""
    summary = f"Recorded output for {_evidence_label(tool).lower()}. Open the native report to inspect its source payload."
    if note:
        summary = f"{summary} {note}"
    return {
        "id": evidence_id,
        "title": _evidence_label(tool),
        "kind": "native research evidence",
        "summary": summary,
        "source": source_path,
        "window": str(split) if isinstance(split, str) and split else "Window not supplied",
        "facts": facts,
        # Keep the exact source trace available to the evidence disclosure
        # view.  The adapter does not summarize or recompute these payloads.
        "args": deepcopy(args),
        "output": deepcopy(payload),
    }


def _hypothesis(hypothesis: dict[str, Any]) -> dict[str, Any]:
    direction = hypothesis.get("direction")
    statement = str(hypothesis.get("statement") or "Recorded hypothesis")
    conditions = [item for item in hypothesis.get("conditions", []) if isinstance(item, str)]
    if direction == "works_worse" and "vol_regime=high" in conditions:
        title = "Large price swings may hurt this strategy."
    elif direction == "works_worse":
        title = "This strategy may be weaker in one condition."
    elif direction == "works_better":
        title = "This strategy may be stronger in one condition."
    else:
        title = "A condition is worth checking."
    return {
        "id": str(hypothesis.get("hypothesis_id") or "hypothesis"),
        "title": title,
        "status": "inconclusive",
        "finding": statement,
        "evidence_ids": [item for item in hypothesis.get("evidence_ids", []) if isinstance(item, str)],
    }


def _source_steps(report: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for index, evidence in enumerate(report.get("evidence") or [], start=1):
        if not isinstance(evidence, dict):
            continue
        evidence_id = evidence.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id:
            continue
        tool = str(evidence.get("tool") or "research check")
        steps.append(
            {
                "id": f"native-source-{index}",
                "role": "Code check",
                "action": "Inspect the recorded source",
                "title": _evidence_label(tool),
                "body": "Stored in the native report for this research stage.",
                "status": "complete",
                "tool": tool,
                "evidence_ids": [evidence_id],
                "timestamp": str(evidence.get("created_at") or report.get("generated_at") or ""),
            }
        )
    return steps


def _limitations(report: dict[str, Any], frozen: dict[str, Any] | None) -> list[str]:
    values: list[str] = []
    diagnostic = report.get("diagnostic") if isinstance(report.get("diagnostic"), dict) else {}
    for item in [*(report.get("limitations") or []), *(diagnostic.get("limitations") or [])]:
        if isinstance(item, str) and item not in values:
            values.append(item)
    additions = [
        "The source report is real, but its original market-data snapshot, date coverage, cost assumptions, and equity series are not attached here.",
        "The native research report records holdout_accessed=false; any separate sealed look is source evidence, not a new candidate arbiter verdict, so approval remains unavailable.",
    ]
    if frozen:
        additions.append("The frozen-look record is source evidence only; it does not rerun the arbiter or turn the candidate into a Keep.")
    for item in additions:
        if item not in values:
            values.append(item)
    return values


def build_virtual_strategy(
    wrapper: dict[str, Any] | None = None,
    strategy_id: str | None = None,
) -> dict[str, Any] | None:
    resolved = _resolve_wrapper(wrapper, strategy_id)
    if not resolved:
        return None
    selected_id, spec, native = resolved
    report = native["report"]
    return {
        "strategy_id": selected_id,
        "name": f"{spec['name']} · Argon report",
        "symbol": "BTCUSDT",
        "timeframe": spec["timeframe"],
        "strategy_version": "argon-native-report",
        "source": "native_report",
        "kind": "positions",
        "status": "ready",
        "synthetic": False,
        "original_dataset_available": False,
        "native_report_available": True,
        "native_source_path": native.get("source_path", spec["report_path"]),
        "n_policies_tried": report.get("n_policies_tried", 0),
        "holdout_accessed": bool(report.get("holdout_accessed")),
        "row_count": 0,
        "date_start": "",
        "date_end": "",
        "dataset_hash": "",
        "created_at": str(report.get("generated_at") or ""),
        "assumptions": {
            "timezone": "Not supplied",
            "fee_bps": None,
            "slippage_bps": None,
            "execution": "Not supplied",
            "description": "Native Argon report only. The source dataset and execution assumptions are not attached.",
        },
    }


def build_virtual_experiment(
    wrapper: dict[str, Any] | None = None,
    strategy_id: str | None = None,
) -> dict[str, Any] | None:
    resolved = _resolve_wrapper(wrapper, strategy_id)
    if not resolved:
        return None
    selected_id, spec, native = resolved
    report = native["report"]
    frozen = _load_frozen_look(selected_id, spec)
    evidence = [
        _evidence_summary(value, str(native.get("source_path") or spec["report_path"]))
        for value in report.get("evidence") or []
        if isinstance(value, dict)
    ]
    evidence = [item for item in evidence if item["id"]]
    diagnostic = report.get("diagnostic") if isinstance(report.get("diagnostic"), dict) else {}
    hypotheses = [_hypothesis(value) for value in diagnostic.get("hypotheses", []) if isinstance(value, dict)]
    champion = report.get("champion_policy_id")

    # Lane A's handoff documents the published KILL for the always-on book.
    # The separate frozen look contains scores, not a new gate arbiter verdict.
    is_meanrev = selected_id == "btc-meanrev-48-demo"
    verdict = "KILL" if is_meanrev and frozen else "INCONCLUSIVE"
    if verdict == "KILL":
        recommendation = "The original strategy failed its risk limits. The proposed filter reduced losses, but still lost money."
    elif report.get("verdict") == "candidate_for_frozen_test":
        recommendation = "A candidate rule was found, but it has not been tested on unseen data."
    else:
        recommendation = "Not proven: no gate met the pre-registered rule."

    native_report = deepcopy(report)
    experiment = {
        "experiment_id": spec["experiment_id"],
        "strategy_id": selected_id,
        "status": "completed",
        "mode": "measured",
        "synthetic": False,
        "source": "native_report",
        "native_report_available": True,
        "native_source_path": native.get("source_path", spec["report_path"]),
        "verdict_source_path": "docs/LANE_A_NOTE_FOR_C.md" if is_meanrev else native.get("source_path", spec["report_path"]),
        "native_report": native_report,
        "strategy_health": deepcopy(report.get("strategy_health")),
        "verdict_scope": "always_on" if is_meanrev and frozen else "candidate",
        "paper_eligible": False,
        "progress": 100,
        "message": "Real native report attached; no new evaluation was run by this workspace.",
        "created_at": str(report.get("generated_at") or ""),
        "policy_id": str(champion or "pending-native-report"),
        "dataset_hash": "",
        "windows": {"train": "Recorded in native report", "validation": "Recorded in native report", "test": "Sealed look attached; dates not supplied" if frozen else "Not accessed"},
        "metrics": [],
        "baselines": [],
        "equity": [],
        "regimes": [],
        "evidence": evidence,
        "steps": _source_steps(report),
        "hypotheses": hypotheses,
        "verdict": verdict,
        "recommendation": recommendation,
        "limitations": _limitations(report, frozen),
        "n_policies_tried": report.get("n_policies_tried", 0),
        "holdout_accessed": bool(report.get("holdout_accessed")),
        "policy": {
            "description": str(champion or "No candidate policy recorded in this report."),
            "conditions": [],
            "holdout_frozen": bool(frozen),
            "test_evaluated": bool(frozen),
        },
    }
    if frozen:
        experiment["frozen_evaluation"] = deepcopy(frozen)
    return experiment


def build_virtual_bundle(
    wrapper: dict[str, Any] | None = None,
    strategy_id: str | None = None,
) -> dict[str, Any] | None:
    resolved = _resolve_wrapper(wrapper, strategy_id)
    if not resolved:
        return None
    selected_id, _spec, native = resolved
    strategy = build_virtual_strategy(native, selected_id)
    experiment = build_virtual_experiment(native, selected_id)
    if not strategy or not experiment:
        return None
    return {"strategy": strategy, "experiment": experiment, "investigation": deepcopy(native)}


def strategy_id_for_experiment(experiment_id: str) -> str | None:
    for strategy_id, spec in NATIVE_REPORTS.items():
        if spec["experiment_id"] == experiment_id:
            return strategy_id
    return None


def is_virtual_strategy(strategy_id: str) -> bool:
    return strategy_id in NATIVE_REPORTS


def is_virtual_experiment(experiment_id: str) -> bool:
    return strategy_id_for_experiment(experiment_id) is not None


__all__ = [
    "DEFAULT_NATIVE_STRATEGY_ID",
    "NATIVE_EXAMPLE_EXPERIMENT_ID",
    "NATIVE_EXAMPLE_STRATEGY_ID",
    "NATIVE_REPORTS",
    "NATIVE_REPORT_STRATEGY_IDS",
    "build_virtual_bundle",
    "build_virtual_experiment",
    "build_virtual_strategy",
    "is_virtual_experiment",
    "is_virtual_strategy",
    "strategy_id_for_experiment",
]
