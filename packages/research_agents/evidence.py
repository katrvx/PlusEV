"""Evidence store: every tool output gets a content-addressed ID. Agents may cite only these."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .models import Evidence


class UnknownEvidenceError(ValueError):
    pass


class EvidenceStore:
    def __init__(self) -> None:
        self._items: dict[str, Evidence] = {}

    def add(self, tool: str, args: dict, payload: dict) -> str:
        blob = json.dumps({"tool": tool, "args": args, "payload": payload}, sort_keys=True, default=str)
        eid = f"ev_{tool[:12]}_{hashlib.sha256(blob.encode()).hexdigest()[:10]}"
        if eid not in self._items:
            self._items[eid] = Evidence(evidence_id=eid, tool=tool, args=args, payload=payload,
                                        created_at=datetime.now(timezone.utc))
        return eid

    def get(self, eid: str) -> Evidence:
        if eid not in self._items:
            raise UnknownEvidenceError(eid)
        return self._items[eid]

    def missing(self, ids: list[str]) -> list[str]:
        return [i for i in ids if i not in self._items]

    def all(self) -> list[Evidence]:
        return list(self._items.values())

    def __contains__(self, eid: str) -> bool:
        return eid in self._items
