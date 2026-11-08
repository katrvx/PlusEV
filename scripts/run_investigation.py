"""Run a Lane B investigation and write the InvestigationReport JSON (what Lane C's UI reads).

    python3 scripts/run_investigation.py                         # deterministic fallback on the Lane A stand-in
    python3 scripts/run_investigation.py --lane-a --fallback    # same agents, Lane A's development view
    python3 scripts/frozen_look.py --report experiments/<committed report>.json   # the one sealed look (ledgered)
    python3 scripts/run_investigation.py --lane-a --fallback --experiment-id btc-meanrev-48-demo   # Lane A's second strategy
    KOK_AGENT_MODEL=google:gemini-3.8-flash GEMINI_API_KEY=... python3 scripts/run_investigation.py   # LLM agents
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "A"))
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from packages.research_agents.investigate import investigate  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment-id", default="fixture")
    ap.add_argument("--fallback", action="store_true", help="force the deterministic agents")
    ap.add_argument("--lane-a", action="store_true", help="load a real Lane A experiment instead of the synthetic stand-in")
    ap.add_argument("--frozen", action="store_true", help="retired: use scripts/frozen_look.py on a committed report")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: experiments/investigation_fixture.json for the stand-in (Lane C labels it synthetic), "
                         "experiments/investigation_lane_a_<strategy>_<mode>.json for --lane-a (real data, never the fixture name)")
    a = ap.parse_args()
    if a.frozen and not a.lane_a:
        raise SystemExit("--frozen scores Lane A's sealed test; pass --lane-a")
    if a.lane_a:
        from kok_a.experiment import load_for_lane_b

        experiment_id = "" if a.experiment_id == "fixture" else a.experiment_id
        loaded = load_for_lane_b(experiment_id)
        report = investigate(experiment_id, loader=lambda _experiment_id: loaded, force_fallback=a.fallback)
        if a.frozen:
            # R4-F4: a re-run investigation may pick a different champion; the look must come from a committed report.
            print("--frozen no longer looks here: commit the report, then run "
                  "python3 scripts/frozen_look.py --report <that report> (one look per policy, ledgered on disk)")
    else:
        report = investigate(a.experiment_id, force_fallback=a.fallback)
    if a.out is None:
        name = f"investigation_lane_a_{report.strategy_id}_{report.agent_mode}.json" if a.lane_a else "investigation_fixture.json"
        a.out = ROOT / "experiments" / name
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
