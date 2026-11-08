"""Read-only API for the real Lane B investigation artifacts.

The report files are produced by the research-agent lane. Part C does not run
agents or infer financial metrics from them; it only validates provenance and
serves the recorded evidence for review.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

try:  # The presentation layer is optional: a missing or broken one must never break report serving.
    from packages.research_agents.recorded import present_report as _present_report
except Exception:  # pragma: no cover - import failure only in a stripped-down checkout
    _present_report = None


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "lane_b_investigation.json"
CHECKED_IN_SYNTHETIC_ARTIFACT = Path("experiments") / "investigation_fixture.json"
REPORT_NAME_PATTERN = re.compile(r"^investigation_[A-Za-z0-9._-]+\.json$")
REPORT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
FROZEN_LOOK_PREFIX = "frozen_look_"
VALID_AGENT_MODES = {"llm", "llm_with_fallback", "deterministic_fallback"}

router = APIRouter(prefix="/api", tags=["investigations"])


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _artifact_paths() -> list[tuple[Path, bool, str]]:
    """Return trusted artifacts with explicit provenance metadata.

    Only the known checked-in fixture path is marked synthetic among local
    artifacts. Arbitrary reports under ``experiments/`` are team artifacts;
    their provenance must not be guessed from their contents or filename.
    """
    experiment_dir = ROOT / "experiments"
    paths = sorted(
        (path for path in experiment_dir.glob("investigation_*.json") if path.is_file() and REPORT_NAME_PATTERN.fullmatch(path.name)),
        key=lambda path: path.name,
    )
    if paths:
        checked_in_fixture = (ROOT / CHECKED_IN_SYNTHETIC_ARTIFACT).resolve()
        return [(path, path.resolve() == checked_in_fixture, "team_artifact") for path in paths]
    if FIXTURE_PATH.is_file():
        return [(FIXTURE_PATH, True, "bundled_lane_b_fixture")]
    return []


def _validate_report(report: Any, path: Path) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise ValueError("root value must be a JSON object")
    required = ("experiment_id", "strategy_id", "generated_at", "agent_mode", "diagnostic", "evidence", "holdout_accessed")
    missing = [field for field in required if field not in report]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    experiment_id = report.get("experiment_id")
    if not isinstance(experiment_id, str) or not REPORT_ID_PATTERN.fullmatch(experiment_id):
        raise ValueError("experiment_id must be a path-safe identifier")
    if report.get("agent_mode") not in VALID_AGENT_MODES:
        raise ValueError("agent_mode must be 'llm', 'llm_with_fallback', or 'deterministic_fallback'")
    if not isinstance(report.get("diagnostic"), dict):
        raise ValueError("diagnostic must be an object")
    if not isinstance(report.get("evidence"), list):
        raise ValueError("evidence must be an array")
    evidence_ids = set[str]()
    for index, evidence in enumerate(report["evidence"]):
        if not isinstance(evidence, dict) or not isinstance(evidence.get("evidence_id"), str) or not evidence["evidence_id"]:
            raise ValueError(f"evidence[{index}] must preserve a non-empty evidence_id")
        if not isinstance(evidence.get("tool"), str) or not evidence["tool"]:
            raise ValueError(f"evidence[{index}] must preserve a non-empty tool")
        evidence_ids.add(evidence["evidence_id"])
    if not isinstance(report["holdout_accessed"], bool):
        raise ValueError("holdout_accessed must be boolean")

    def validate_references(value: Any, path: tuple[str, ...] = ()) -> None:
        # Evidence records are definitions, not references to validate.
        if path == ("evidence",):
            return
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = path + (str(key),)
                if key == "evidence_ids":
                    if not isinstance(child, list):
                        raise ValueError(f"{'.'.join(child_path)} must be an array")
                    for reference in child:
                        if not isinstance(reference, str) or reference not in evidence_ids:
                            raise ValueError(f"{'.'.join(child_path)} references unknown evidence_id {reference!r}")
                    continue
                if key == "evidence_id":
                    if child is None and path and path[0] == "trial_log":
                        continue
                    if not isinstance(child, str) or child not in evidence_ids:
                        raise ValueError(f"{'.'.join(child_path)} references unknown evidence_id {child!r}")
                    continue
                validate_references(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                validate_references(child, path + (str(index),))

    validate_references(report)
    return report


def _frozen_look(report: dict[str, Any]) -> dict[str, Any] | None:
    """Return the one pre-registered test-window look recorded for this report, if any.

    The file is ``experiments/frozen_look_<strategy_id>.json``. It is attached only
    when it names the same strategy and experiment as the report, so a look from
    an older or different investigation is never shown against this one.
    """
    strategy_id = report.get("strategy_id")
    if not isinstance(strategy_id, str) or not REPORT_ID_PATTERN.fullmatch(strategy_id):
        return None
    path = ROOT / "experiments" / f"{FROZEN_LOOK_PREFIX}{strategy_id}.json"
    if not path.is_file():
        return None
    try:
        look = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid frozen-look artifact {_relative(path)}: {exc.msg} at line {exc.lineno}") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not read frozen-look artifact {_relative(path)}: {exc}") from exc
    if not isinstance(look, dict) or not isinstance(look.get("evaluation"), dict):
        raise HTTPException(status_code=500, detail=f"Invalid frozen-look artifact {_relative(path)}: missing evaluation object")
    if look.get("strategy_id") != strategy_id or look.get("experiment_id") != report.get("experiment_id"):
        return None
    return look


def _presentation(report: dict[str, Any], source_path: str) -> dict[str, Any] | None:
    """Plain-language view of one report, or None. Never raises.

    A report that already carries ``presentation`` is served as recorded. Otherwise
    the view is computed by code from the report (and, for the two recorded runs,
    the published verdict and the one held-out look). It adds no numbers.
    """
    recorded = report.get("presentation")
    if isinstance(recorded, dict):
        return recorded
    if _present_report is None:
        return None
    try:
        return _present_report(json.loads(json.dumps(report)), source_path).model_dump(mode="json")
    except Exception:
        return None


def _load_wrapper(path: Path, synthetic: bool, source: str) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Investigation artifact disappeared: {_relative(path)}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid investigation artifact {_relative(path)}: {exc.msg} at line {exc.lineno}") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not read investigation artifact {_relative(path)}: {exc}") from exc
    try:
        validated = _validate_report(report, path)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid investigation artifact {_relative(path)}: {exc}") from exc
    wrapper: dict[str, Any] = {
        "source": source,
        "synthetic": synthetic,
        "source_path": _relative(path),
        "report": validated,
    }
    frozen_look = _frozen_look(validated)
    if frozen_look is not None:
        wrapper["frozen_look"] = frozen_look
    wrapper["presentation"] = _presentation(validated, wrapper["source_path"])
    return wrapper


def _load_wrappers() -> list[dict[str, Any]]:
    return [_load_wrapper(path, synthetic, source) for path, synthetic, source in _artifact_paths()]


def _summary(wrapper: dict[str, Any]) -> dict[str, Any]:
    report = wrapper["report"]
    diagnostic = report.get("diagnostic") or {}
    return {
        "experiment_id": report["experiment_id"],
        "strategy_id": report["strategy_id"],
        "generated_at": report["generated_at"],
        "agent_mode": report["agent_mode"],
        "model_id": report.get("model_id"),
        "holdout_accessed": report.get("holdout_accessed", False),
        "source": wrapper["source"],
        "synthetic": wrapper["synthetic"],
        "source_path": wrapper["source_path"],
        "diagnostic_summary": diagnostic.get("summary", ""),
        "hypothesis_count": len(diagnostic.get("hypotheses") or []),
        "proposal_count": len(report.get("proposals") or []),
        "trial_count": len(report.get("trial_log") or []),
        "evidence_count": len(report.get("evidence") or []),
        "n_policies_tried": report.get("n_policies_tried", 0),
        "strategy_health": _health_summary(report.get("strategy_health")),
        **_presentation_summary(wrapper.get("presentation")),
    }


def _presentation_summary(presentation: Any) -> dict[str, Any]:
    """Optional list fields: the plain-language finding and the filter counts."""
    if not isinstance(presentation, dict):
        return {"headline": None, "filter_counts": None}
    headline = presentation.get("headline") if isinstance(presentation.get("headline"), dict) else {}
    counts = presentation.get("filter_counts")
    return {
        "headline": {"finding": headline.get("finding"), "verdict_label": headline.get("verdict_label")} if headline else None,
        "filter_counts": counts if isinstance(counts, dict) else None,
    }


def _health_summary(health: Any) -> dict[str, Any] | None:
    if not isinstance(health, dict):
        return None
    blocks = health.get("validation_blocks") or []
    if not isinstance(blocks, list):
        blocks = []
    return {
        "status": health.get("status"),
        "summary": health.get("summary"),
        "n_blocks": len(blocks),
        "n_below": sum(1 for block in blocks if isinstance(block, dict) and block.get("position") == "below"),
        "n_above": sum(1 for block in blocks if isinstance(block, dict) and block.get("position") == "above"),
        "n_inside": sum(1 for block in blocks if isinstance(block, dict) and block.get("position") == "inside"),
    }


def _safe_report_id(experiment_id: str) -> str:
    if not REPORT_ID_PATTERN.fullmatch(experiment_id):
        raise HTTPException(status_code=400, detail="Invalid experiment_id")
    return experiment_id


def _find_wrapper(experiment_id: str) -> dict[str, Any]:
    safe_id = _safe_report_id(experiment_id)
    wrappers = _load_wrappers()
    for wrapper in wrappers:
        if wrapper["report"].get("experiment_id") == safe_id:
            return wrapper
    raise HTTPException(status_code=404, detail=f"Investigation not found: {safe_id}")


@router.get("/investigations")
def list_investigations() -> list[dict[str, Any]]:
    """List report metadata without dropping invalid trusted artifacts silently."""
    return [_summary(wrapper) for wrapper in _load_wrappers()]


@router.get("/investigations/{experiment_id}")
def get_investigation(experiment_id: str) -> dict[str, Any]:
    """Return one validated report, including raw Lane B evidence payloads."""
    return _find_wrapper(experiment_id)


__all__ = ["FIXTURE_PATH", "ROOT", "get_investigation", "list_investigations", "router"]
