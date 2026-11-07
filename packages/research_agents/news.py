"""Point-in-time news records (AGENTS.md Lane B step 6, spec section 7).

Rules enforced here:
- a record is visible at time t only if first_seen_at <= t (not merely published_at);
- every record keeps url, source and a content hash, so claims stay checkable;
- no claim of a historical backfill we don't have: coverage is reported per window,
  and only from inside the window (no timestamps from outside it leak through).
Semantic labels are optional and come from a labeller (LLM or FinBERT) run in batch;
the labeller only ever sees the stored text, never prices or returns.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

EventTopic = Literal["risk_on_off", "regulatory", "macro", "exchange_failure", "institutional_flows", "other"]


def as_utc(value: str | datetime) -> datetime:
    """Parse ISO strings / datetimes; naive values are treated as UTC."""
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class NewsLabel(BaseModel):
    topic: EventTopic
    polarity: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    labeller: str                       # e.g. "llm:gemini-flash" or "finbert" or "manual"


class NewsRecord(BaseModel):
    news_id: str
    url: str
    source: str
    title: str
    published_at: datetime
    first_seen_at: datetime             # when we (or the archive) first saw it; may be later than published_at
    content_hash: str
    symbols: list[str] = Field(default_factory=list)
    label: NewsLabel | None = None


def content_hash(title: str, body: str = "") -> str:
    return "sha256:" + hashlib.sha256((title + "\n" + body).encode()).hexdigest()


class NewsStore:
    def __init__(self, records: list[NewsRecord]):
        self.records = sorted(records, key=lambda r: as_utc(r.first_seen_at))

    @classmethod
    def from_jsonl(cls, path: Path) -> "NewsStore":
        rows = [NewsRecord.model_validate(json.loads(l)) for l in path.read_text().splitlines() if l.strip()]
        return cls(rows)

    def visible(self, start: datetime, end: datetime, cutoff: datetime, symbol: str | None = None) -> list[NewsRecord]:
        """Records first seen in [start, end] AND not after the decision cutoff."""
        start, end, cutoff = as_utc(start), as_utc(end), as_utc(cutoff)
        out = []
        for r in self.records:
            seen = as_utc(r.first_seen_at)
            if seen > cutoff:
                break
            if start <= seen <= end and (symbol is None or not r.symbols or symbol in r.symbols):
                out.append(r)
        return out

    def coverage(self, start: datetime, end: datetime) -> dict:
        start, end = as_utc(start), as_utc(end)
        inside = [r for r in self.records if start <= as_utc(r.first_seen_at) <= end]
        return {
            "records_in_window": len(inside),
            "labelled": sum(r.label is not None for r in inside),
            "first_in_window": as_utc(inside[0].first_seen_at).isoformat() if inside else None,
            "last_in_window": as_utc(inside[-1].first_seen_at).isoformat() if inside else None,
        }


class Labeller(Protocol):
    name: str

    def label(self, title: str) -> NewsLabel: ...
