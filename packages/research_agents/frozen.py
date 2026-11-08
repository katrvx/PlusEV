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


def record(entry: dict, path: Path = LEDGER) -> None:
    check(entry["spec_hash"], path)
    rows = load(path)
    rows.append({**entry, "recorded_at": datetime.now(timezone.utc).isoformat()})
    path.write_text(json.dumps(rows, indent=2) + "\n")
