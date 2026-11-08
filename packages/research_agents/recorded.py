"""The recorded real-data runs, with their published strategy verdicts and the one held-out look.

One place for these facts, so the API, the UI and the readable reports say the same thing. The strategy verdicts are
Lane A's arbiter results on the 2018-02 → 2026-10 BTCUSDT book (A/README.md); they apply to the ORIGINAL strategy,
always on, not to any agent filter.
"""

from __future__ import annotations

import json
from pathlib import Path

from .presentation import ReportPresentation, present

ROOT = Path(__file__).resolve().parents[2]

WINDOWS = {
    "train": "2018-02-08 to 2023-05-07",
    "validation": "2023-05-07 to 2025-02-02",
    "test": "2025-02-02 to 2026-10-31",
}

RECORDED_RUNS = {
    "btc-trend-24-72-demo": {
        "report": "experiments/investigation_argon_lane_a.json",
        "held_out": None,
        "published": {
            "verdict": "INCONCLUSIVE",
            "source": "Lane A arbiter",
            "scope": "the original strategy, always on",
            "reason": "the held-out intervals still contain zero, and the critic rejected every proposed filter.",
        },
    },
    "btc-meanrev-48-demo": {
        "report": "experiments/investigation_argon_meanrev.json",
        "held_out": "experiments/frozen_look_btc-meanrev-48-demo.json",
        "published": {
            "verdict": "KILL",
            "source": "Lane A arbiter",
            "scope": "the original strategy, always on",
            "reason": ("held-out drawdown 60.4% is past the 40% cap and its net-return interval is entirely below "
                       "zero. The agents' filter is not part of this verdict."),
        },
    },
}


def recorded_for_report(report_path: str) -> tuple[str, dict] | None:
    for sid, run in RECORDED_RUNS.items():
        if run["report"] == report_path:
            return sid, run
    return None


def present_report(report: dict, report_path: str | None = None) -> ReportPresentation:
    """Presentation for any report; recorded runs also get their held-out look and published verdict."""
    found = recorded_for_report(report_path) if report_path else None
    if found and report.get("strategy_id") == found[0]:
        run = found[1]
        look = json.loads((ROOT / run["held_out"]).read_text()) if run["held_out"] else None
        if look and look.get("experiment_id") != report.get("experiment_id"):
            look = None                                    # never attach a look taken for another run
        tpath = ROOT / "experiments" / "conditions_check" / f"timing_{found[0]}.json"
        timing = json.loads(tpath.read_text()) if tpath.exists() else None
        if timing and timing.get("experiment_id") != report.get("experiment_id"):
            timing = None
        if timing:
            timing["_path"] = tpath.relative_to(ROOT).as_posix()
        return present(report, held_out=look, published=run["published"], windows=WINDOWS,
                       report_path=report_path, held_out_path=run["held_out"] if look else None, timing_check=timing)
    return present(report, report_path=report_path)


__all__ = ["RECORDED_RUNS", "WINDOWS", "present_report", "recorded_for_report"]
