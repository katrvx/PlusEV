"""JSONL adapter for the organisers' AgentVerse finance kit (`run` / `challenge`).

    python3 -m packages.kit_adapter.kok --strategy mean_reversion --mode gated
    python3 -m packages.kit_adapter.kok --strategy trend --mode raw

One JSON request per stdin line, one JSON response per stdout line, flushed.
Diagnostics go to stderr only. Each `market_step` sees the price history up to
the current bar; the target is recomputed from that history alone, so the
adapter keeps no state between requests and cannot see future bars.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback

from . import rule


def respond(request: dict, strategy: str, mode: str) -> dict:
    if request.get("task") != "market_step":
        return {"error": "unsupported_task"}
    data = request["input"]
    prices = [int(bar["price_pence"]) for bar in data["history"]]
    target = float(rule.target_positions(strategy, mode, prices)[-1])
    return {"action": rule.kit_action(target, int(data["shares"]))}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", choices=sorted(rule.STRATEGY_IDS), required=True)
    ap.add_argument("--mode", choices=("raw", "gated"), required=True)
    args = ap.parse_args(argv)
    print(f"kok adapter ready: strategy={args.strategy} mode={args.mode} vol_window={rule.VOL_WINDOW}", file=sys.stderr)

    for line in sys.stdin:
        if not line.strip():
            continue
        rid = None
        try:
            req = json.loads(line)
            rid = req.get("request_id")
            out = respond(req, args.strategy, args.mode)
            if out.get("action") in ("buy", "sell"):
                print(f"[{rid}] {out['action']}", file=sys.stderr)
        except Exception as error:  # visible per-case error in the kit report, details in stderr
            traceback.print_exc(file=sys.stderr)
            out = {"error": f"adapter_exception: {type(error).__name__}"}
        sys.stdout.write(json.dumps({"request_id": rid, "output": out}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
