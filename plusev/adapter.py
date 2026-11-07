"""JSONL adapter for the organisers' test bench (finance kit `bench.py run|challenge|live`).

    python3 -m plusev.adapter --strategy trend --mode governed
    python3 -m plusev.adapter --strategy trend --mode raw

Reads one request per line on stdin, writes one response per line on stdout and
flushes. All diagnostics go to stderr: a single stray print to stdout breaks the run.
Calls exactly the same strategy and governor code the app uses.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import governor as gv
from .execution import strategy_decider
from .strategies import STRATEGIES

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", choices=sorted(STRATEGIES), default="trend")
    ap.add_argument("--mode", choices=("raw", "governed"), default="governed")
    args = ap.parse_args()

    if args.mode == "governed":
        decide = gv.load(args.strategy, ROOT).decide
    else:
        decide = strategy_decider(STRATEGIES[args.strategy])

    for line in sys.stdin:
        if not line.strip():
            continue
        req = json.loads(line)
        rid = req.get("request_id")
        if req.get("task") != "market_step":
            out = {"error": "unsupported_task"}
        else:
            data = req["input"]
            prices = [bar["price_pence"] for bar in data["history"]]
            action, why = decide(prices, int(data["shares"]))
            print(f"[{rid}] {action}: {why}", file=sys.stderr)
            out = {"action": action}
        sys.stdout.write(json.dumps({"request_id": rid, "output": out}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
