"""The one sealed-test look for a Lane B champion, from a COMMITTED report.

    python3 scripts/frozen_look.py --report experiments/investigation_argon_meanrev.json

Refuses unless: the report is committed and unchanged in git (the champion is on record before the
look); it names an accepted champion; the champion's spec hash is not already in
experiments/frozen_ledger.json; and the loader rebuilds the same experiment id. Writes
experiments/frozen_look_<strategy>.json and appends the ledger. Cash is 0, so delta vs cash = net.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "A"))
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from packages.research_agents import frozen  # noqa: E402
from packages.research_agents.tools import spec_hash  # noqa: E402


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args()
    rel = str(a.report.resolve().relative_to(ROOT))
    try:
        _git("ls-files", "--error-unmatch", rel)
    except subprocess.CalledProcessError:
        raise SystemExit(f"{rel} is not committed: commit the report that chose the champion first")
    if _git("status", "--porcelain", "--", rel):
        raise SystemExit(f"{rel} has uncommitted changes: the look must use the committed champion")
    report = json.loads(a.report.read_text())
    accepted = [c for c in report["candidates"] if c["status"] == "accepted_for_frozen_test"]
    if not accepted:
        raise SystemExit("the report has no accepted champion: nothing to look at")
    champ = accepted[0]["policy_spec"]
    h = spec_hash(champ)
    frozen.check(h)
    frozen.check_window(report["experiment_id"])   # one look per test window, whatever the policy

    from kok_a.experiment import load_for_lane_b, score_frozen
    exp, runner, *_ = load_for_lane_b(report["strategy_id"])
    if exp.experiment_id != report["experiment_id"]:
        raise SystemExit(f"loader rebuilt {exp.experiment_id}, report is {report['experiment_id']}: data changed, no look")
    [ev] = score_frozen(runner, [champ])
    artifact = f"experiments/frozen_look_{report['strategy_id']}.json"
    out = {"what": "the one sealed-test look for the Lane B champion accepted by the pre-registered rule",
           "experiment_id": report["experiment_id"], "strategy_id": report["strategy_id"],
           "champion_policy_id": champ["policy_id"], "champion_spec_hash": h, "selected_in_report": rel,
           "report_committed_before_look": _git("log", "-1", "--format=%h", "--", rel),
           "looked_at": datetime.now(timezone.utc).isoformat(), "delta_vs_cash": ev.metrics.net_return,
           "evaluation": ev.model_dump(mode="json")}
    (ROOT / artifact).write_text(json.dumps(out, indent=2))
    frozen.record({"spec_hash": h, "experiment_id": report["experiment_id"], "policy_id": champ["policy_id"],
                   "looked_at": out["looked_at"], "artifact": artifact})
    print(f"sealed look: {champ['policy_id']} net {ev.metrics.net_return:+.4f}, delta vs always-on "
          f"{ev.delta_net_return_vs_always_on:+.4f} (90% CI {ev.ci_delta[0]:+.4f}..{ev.ci_delta[1]:+.4f}) -> {artifact}")


if __name__ == "__main__":
    main()
