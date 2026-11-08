"""One sealed look per policy, enforced on disk (adversarial review round 4, F4).

Lane A's GateRunner remembers sealed looks in memory only, so a new process, a renamed policy or a
re-run investigation could take another look. This ledger keys every look by the policy's canonical
spec hash (names do not matter) and refuses a second one. scripts/frozen_look.py is the only writer.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / "experiments" / "frozen_ledger.json"


class AlreadyLooked(RuntimeError):
    pass


def load(path: Path = LEDGER) -> list[dict]:
    return json.loads(path.read_text()) if path.is_file() else []


def check(spec_hash: str, path: Path = LEDGER) -> None:
    prior = [e for e in load(path) if e["spec_hash"] == spec_hash]
    if prior:
        raise AlreadyLooked(f"policy {spec_hash} already had its sealed look on {prior[0]['looked_at']} "
                            f"({prior[0]['artifact']}); a second look is refused")


class WindowAlreadyOpened(RuntimeError):
    pass


def check_window(experiment_id: str, path: Path = LEDGER) -> None:
    """One held-out look per experiment (same strategy, same data, same test window), whatever the policy.

    Once a test window has been opened, its result is diagnostic only: choosing a different filter afterwards and
    looking again would be selection on the test. A new acceptance needs fresh unseen data (a new experiment)."""
    prior = [e for e in load(path) if e.get("experiment_id") == experiment_id]
    if prior:
        raise WindowAlreadyOpened(
            f"the held-out window of {experiment_id} was already opened on {prior[0]['looked_at']} for "
            f"{prior[0]['policy_id']} ({prior[0]['artifact']}); any new acceptance needs fresh data, not a second look")


def record(entry: dict, path: Path = LEDGER) -> None:
    check(entry["spec_hash"], path)
    check_window(entry["experiment_id"], path)
    rows = load(path)
    rows.append({**entry, "recorded_at": datetime.now(timezone.utc).isoformat()})
    path.write_text(json.dumps(rows, indent=2) + "\n")
