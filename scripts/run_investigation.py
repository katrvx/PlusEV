"""Run a Lane B investigation and write the InvestigationReport JSON (what Lane C's UI reads).

    python3 scripts/run_investigation.py                         # deterministic fallback on the Lane A stand-in
    python3 scripts/run_investigation.py --lane-a --fallback    # same agents, Lane A's development view
    python3 scripts/run_investigation.py --lane-a --fallback --frozen   # one sealed look at the accepted champion
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
    ap.add_argument("--frozen", action="store_true", help="with --lane-a, score each accepted candidate once on the sealed test")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: experiments/investigation_fixture.json for the stand-in (Lane C labels it synthetic), "
                         "experiments/investigation_lane_a_<strategy>_<mode>.json for --lane-a (real data, never the fixture name)")
    a = ap.parse_args()
    if a.frozen and not a.lane_a:
        raise SystemExit("--frozen scores Lane A's sealed test; pass --lane-a")
    if a.lane_a:
        from kok_a.experiment import load_for_lane_b, score_frozen

        experiment_id = "" if a.experiment_id == "fixture" else a.experiment_id
        loaded = load_for_lane_b(experiment_id)
        report = investigate(experiment_id, loader=lambda _experiment_id: loaded, force_fallback=a.fallback)
        if a.frozen:
            accepted = [c.policy_spec for c in report.candidates if c.status == "accepted_for_frozen_test"]
            print(f"sealed test, {len(accepted)} accepted candidate(s), one look each")
            for evaluation in score_frozen(loaded[1], accepted):
                print(
                    f"  {evaluation.policy_id:28s} net {evaluation.metrics.net_return:+.4f}  "
                    f"delta {evaluation.delta_net_return_vs_always_on:+.4f}"
                )
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
