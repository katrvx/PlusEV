"""Check that our execution engine reproduces the organisers' runner to the penny.

Runs the kit's `bench.py run` with our adapter (raw and governed) on a dataset and
compares final cash per path against plusev.execution.simulate. Writes eval/mvp/kit_check.json.

    python3 scripts/kit_check.py --dataset data/kit-dev --kit <kit folder>/bench.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plusev import governor as gv, regime as rg  # noqa: E402
from plusev.execution import simulate, strategy_decider  # noqa: E402
from plusev.strategies import STRATEGIES  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=ROOT / "data/kit-dev")
    ap.add_argument("--kit", type=Path, default=ROOT / "agentverse" / "finance" / "bench.py")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    thr = rg.load(ROOT / "envelopes/regime_thresholds.json")
    cases = {}
    for line in (args.dataset / "inputs.jsonl").read_text().splitlines():
        row = json.loads(line)
        cases[row["case_id"]] = row["input"]

    results, tmp = [], Path(tempfile.mkdtemp())
    for name in STRATEGIES:
        for mode in ("raw", "governed"):
            out = tmp / f"{name}-{mode}"
            subprocess.run(
                [sys.executable, str(args.kit), "run", "--dataset", str(args.dataset), "--output", str(out),
                 "--limit", str(args.limit), "--max-seconds", "900",
                 "--adapter", sys.executable, "-m", "plusev.adapter", "--strategy", name, "--mode", mode],
                cwd=ROOT, capture_output=True, check=False,
            )
            decide = strategy_decider(STRATEGIES[name]) if mode == "raw" else gv.load(name, ROOT).decide
            rows = [json.loads(l) for l in (out / "case-results.jsonl").read_text().splitlines()]
            mismatches = sum(simulate(cases[r["case_id"]], decide, thr)["final_cash_pence"] != r["output"]["final_cash_pence"] for r in rows)
            results.append({"strategy": name, "mode": mode, "paths": len(rows), "mismatches": mismatches})
            print(results[-1], file=sys.stderr)
    shutil.rmtree(tmp, ignore_errors=True)
    total = sum(r["paths"] for r in results)
    bad = sum(r["mismatches"] for r in results)
    (ROOT / "eval/mvp/kit_check.json").write_text(json.dumps({"dataset": args.dataset.name, "runs": results, "total_paths": total, "total_mismatches": bad}, indent=2))
    print(f"{bad} mismatches in {total} path runs", file=sys.stderr)


if __name__ == "__main__":
    main()
