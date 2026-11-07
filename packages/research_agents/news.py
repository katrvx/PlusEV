"""Point-in-time news records (AGENTS.md Lane B step 6, spec section 7).

Rules enforced here:
- a record is visible at time t only if first_seen_at <= t (not merely published_at);
- every record keeps url, source and a content hash, so claims stay checkable;
- no claim of a historical backfill we don't have: coverage is reported per window.
Semantic labels are optional and come from a labeller (LLM or FinBERT) run in batch;
the labeller only ever sees the stored text, never prices or returns.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

EventTopic = Literal["risk_on_off", "regulatory", "macro", "exchange_failure", "institutional_flows", "other"]


class NewsLabel(BaseModel):
    topic: EventTopic
    polarity: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    labeller: str                       # e.g. "gemini-flash@2026-11-07" or "finbert" or "manual"


class NewsRecord(BaseModel):
    news_id: str
    url: str
    source: str
    title: str
    published_at: datetime
    first_seen_at: datetime             # when WE (or the archive) first saw it; may be later than published_at
    content_hash: str
    symbols: list[str] = Field(default_factory=list)
    label: NewsLabel | None = None


def content_hash(title: str, body: str = "") -> str:
    return "sha256:" + hashlib.sha256((title + "\n" + body).encode()).hexdigest()


class NewsStore:
    def __init__(self, records: list[NewsRecord]):
        self.records = sorted(records, key=lambda r: r.first_seen_at)

    @classmethod
    def from_jsonl(cls, path: Path) -> "NewsStore":
        rows = [NewsRecord.model_validate(json.loads(l)) for l in path.read_text().splitlines() if l.strip()]
        return cls(rows)

    def visible(self, start: datetime, end: datetime, cutoff: datetime, symbol: str | None = None) -> list[NewsRecord]:
        """Records first seen in [start, end] AND not after the decision cutoff."""
        out = []
        for r in self.records:
            if r.first_seen_at > cutoff:
                break
            if start <= r.first_seen_at <= end and (symbol is None or not r.symbols or symbol in r.symbols):
                out.append(r)
        return out

    def coverage(self, start: datetime, end: datetime) -> dict:
        inside = [r for r in self.records if start <= r.first_seen_at <= end]
        return {
            "records_in_window": len(inside),
            "labelled": sum(r.label is not None for r in inside),
            "earliest_record": self.records[0].first_seen_at.isoformat() if self.records else None,
            "latest_record": self.records[-1].first_seen_at.isoformat() if self.records else None,
        }


class Labeller(Protocol):
    name: str

    def label(self, title: str) -> NewsLabel: ...
