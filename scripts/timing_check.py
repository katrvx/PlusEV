"""Timing vs taking less risk, for gates already chosen in a committed report. Training and Validation only.

For each agent gate in the report, with identical costs on the same Validation window:
  the gate, the original strategy (always on), cash, constant half size, a constant frozen at the gate's average
  TRAIN size (same average exposure, no timing), the simple rule and Lane A's regime filter.
A gate that beats always-on but not the same-size constant won by holding less, not by choosing when.

Diagnostic only: the selection rule was fixed before the run and is not changed here, and the held-out test is never
read (GateRunner.evaluate refuses it). Run:
  python3 scripts/timing_check.py --report experiments/investigation_argon_meanrev.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "A"))

from packages.research_agents.tools import spec_hash  # noqa: E402

HALF = {"policy_id": "benchmark::half_size", "family": "constant", "allocation": 0.5}


def row(name: str, spec: dict, ev, role: str) -> dict:
    m = ev.metrics
    return {"name": name, "role": role, "policy_id": spec.get("policy_id"), "spec_hash": spec_hash(spec), "spec": spec,
            "net_return": m.net_return, "ci_net_return": m.ci_net_return, "max_drawdown": m.max_drawdown,
            "exposure": m.exposure, "sharpe": m.sharpe, "turnover": m.turnover,
            "delta_vs_always_on": ev.delta_net_return_vs_always_on, "ci_delta_vs_always_on": ev.ci_delta,
            "allocation_mix": ev.allocation_mix, "audit_id": ev.audit_id}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    report = json.loads((ROOT / a.report).read_text())
    from kok_a.experiment import load_for_lane_b

    _, runner, _, _, _ = load_for_lane_b(report["strategy_id"])
    always = {"policy_id": "always_on", "family": "always_on"}
    cash = {"policy_id": "cash", "family": "cash"}
    refs = [("Original strategy (always on)", always, "benchmark"), ("Cash", cash, "benchmark"),
            ("Constant half size", HALF, "benchmark")]
    if getattr(runner, "rule_spec", None):
        refs.append(("Simple rule", runner.rule_spec, "reference"))
    if getattr(runner, "regime_spec", None):
        refs.append(("Lane A regime filter (current)", runner.regime_spec, "reference"))
    rows = [row(n, s, runner.evaluate(s, "validation"), r) for n, s, r in refs]
    gates = []
    for c in report["candidates"]:
        if c["source"] != "agent":
            continue
        spec = c["policy_spec"]
        train = runner.evaluate(spec, "train")
        size = sum(float(k) * float(v) for k, v in train.allocation_mix.items())
        matched = {"policy_id": f"benchmark::exposure_matched::{spec['policy_id']}", "family": "constant",
                   "allocation": round(size, 6), "matched_on": "train"}
        g = row(c["policy_id"], spec, runner.evaluate(spec, "validation"), "agent gate")
        mt = row(f"Constant {size:.3f}x (same average Training size as {spec['policy_id']})", matched,
                 runner.evaluate(matched, "validation"), "benchmark")
        ao = next(r for r in rows if r["policy_id"] == "always_on")
        vsize = (g["exposure"] / ao["exposure"]) if ao["exposure"] else 0.0
        realized = {"policy_id": f"benchmark::validation_size::{spec['policy_id']}", "family": "constant",
                    "allocation": round(min(1.0, max(0.0, vsize)), 6), "matched_on": "validation (diagnostic)"}
        rz = row(f"Constant {vsize:.3f}x (the gate's actual Validation size; diagnostic, set on Validation)", realized,
                 runner.evaluate(realized, "validation"), "diagnostic")
        g["validation_average_size"] = vsize
        g["vs_validation_size"] = g["net_return"] - rz["net_return"]
        half = next(r for r in rows if r["policy_id"] == "benchmark::half_size")
        g["status_in_report"] = c["status"]
        g["train_average_size"] = size
        g["vs_half_size"] = g["net_return"] - half["net_return"]
        g["vs_matched_exposure"] = g["net_return"] - mt["net_return"]
        g["vs_cash"] = g["net_return"]
        beats = [g["vs_matched_exposure"] > 0, g["vs_half_size"] > 0, g["vs_validation_size"] > 0]
        g["timing_read"] = ("beats half size and constants at both its Training and its Validation average size: "
                            "evidence of timing on Validation (not proof; Validation was also used to select)"
                            if all(beats) else
                            "does not beat every constant of the same size: part or all of the gain is from holding less")
        if abs(vsize - size) > 0.1:
            g["size_shift_note"] = (f"average size moved from {size:.2f}x on Training to {vsize:.2f}x on Validation: "
                                    "the condition's frequency changed, so the Training-matched constant is a loose comparison")
        gates += [g, mt, rz]
    out = {
        "what": "timing vs taking less risk, Validation only, identical costs (10 bp fee + 1 bp slippage, next-bar fills)",
        "report": a.report, "experiment_id": report["experiment_id"], "strategy_id": report["strategy_id"],
        "computed_at": datetime.now(timezone.utc).isoformat(), "split": "validation",
        "held_out_test_read": False,
        "note": ("Diagnostic. The selection rule fixed before the run is unchanged; a timing requirement would be a new "
                 "acceptance criterion and needs fresh unseen data (after 2026-10-31). Net returns are compounded, after costs."),
        "benchmarks": rows, "gates": gates,
    }
    path = ROOT / (a.out or f"experiments/conditions_check/timing_{report['strategy_id']}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, default=str) + "\n")
    for r in rows + gates:
        extra = (f"  vs train-size {r['vs_matched_exposure']:+.1%}  vs val-size {r['vs_validation_size']:+.1%}  vs half {r['vs_half_size']:+.1%}"
                 if "vs_matched_exposure" in r else "")
        print(f"{r['name'][:62]:62s} net {r['net_return']:+8.1%}  exp {r['exposure']:.2f}  dd {r['max_drawdown']:.1%}{extra}")
    print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
