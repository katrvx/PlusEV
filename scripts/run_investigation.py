"""Run a Lane B investigation and write the InvestigationReport JSON (what Lane C's UI reads).

    python3 scripts/run_investigation.py                         # deterministic fallback on the Lane A stand-in
    KOK_AGENT_MODEL=google:gemini-2.5-flash GEMINI_API_KEY=... python3 scripts/run_investigation.py   # LLM agents
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from packages.research_agents.investigate import investigate  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment-id", default="fixture")
    ap.add_argument("--fallback", action="store_true", help="force the deterministic agents")
    ap.add_argument("--out", type=Path, default=ROOT / "experiments" / "investigation_fixture.json")
    a = ap.parse_args()
    report = investigate(a.experiment_id, force_fallback=a.fallback)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(report.model_dump_json(indent=2))
    print(f"mode={report.agent_mode} model={report.model_id} policies_tried={report.n_policies_tried} "
          f"evidence={len(report.evidence)} holdout_accessed={report.holdout_accessed}")
    print(report.diagnostic.summary)
    for c in report.candidates:
        print(f"  {c.policy_id:28s} {c.status:26s} {' | '.join(c.reasons)}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
