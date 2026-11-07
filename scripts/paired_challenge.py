"""Hidden-test evidence with a paired baseline.

Step 1 (claimable result): run the organisers' challenge with the GOVERNED bot.
Fresh secret seed, cases only in memory, commitment written before the run.

    python3 scripts/paired_challenge.py challenge --strategy mean_reversion --pack markets --cases 300

Step 2 (paired baseline): after the run the kit publishes the seed in the challenge
folder. Pass it explicitly; the same cases are rebuilt and the RAW bot is run on them,
so raw vs governed is compared path by path on identical hidden paths.

    python3 scripts/paired_challenge.py replay --strategy mean_reversion --pack markets --cases 300 --seed <revealed seed>

Writes eval/challenge/<pack>-<strategy>/{governed/, raw-replay/, paired.json}.
`real-markets` replay needs internet (same Binance windows are re-downloaded).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "agentverse" / "finance" / "bench.py"


def kit(*args: str) -> None:
    subprocess.run([sys.executable, str(KIT), *args], cwd=ROOT, check=True, capture_output=True)


def adapter(strategy: str, mode: str) -> list[str]:
    return ["--adapter", sys.executable, "-m", "plusev.adapter", "--strategy", strategy, "--mode", mode]


def rows(folder: Path) -> dict:
    out = {}
    for line in (folder / "case-results.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r.get("output") and "final_cash_pence" in r["output"]:
            out[r["case_id"]] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("challenge", "replay"))
    ap.add_argument("--strategy", default="mean_reversion")
    ap.add_argument("--pack", default="markets", choices=("markets", "real-markets"))
    ap.add_argument("--cases", type=int, default=300)
    ap.add_argument("--seed", type=int, help="the seed the kit revealed after the challenge (replay step)")
    a = ap.parse_args()

    base = ROOT / "eval/challenge" / f"{a.pack}-{a.strategy}"
    gov_dir, raw_dir = base / "governed", base / "raw-replay"
    if a.step == "challenge":
        base.mkdir(parents=True, exist_ok=False)
        kit("challenge", "--pack", a.pack, "--cases", str(a.cases), "--project", str(ROOT), "--output", str(gov_dir),
            "--max-seconds", "1800", *adapter(a.strategy, "governed"))
        print(f"done: {gov_dir}. Now run the replay step with the revealed seed from that folder.")
        return
    if a.seed is None:
        sys.exit("replay needs --seed (published by the kit in the challenge folder after the run)")
    seed = a.seed

    if a.pack == "markets":
        ds = base / "revealed-cases"
        kit("generate", "--pack", "markets", "--cases", str(a.cases), "--seed", str(seed), "--output", str(ds))
    else:
        ds = base / "revealed-cases"
        kit("fetch", "--cases", str(a.cases), "--seed", str(seed), "--output", str(ds))
    kit("run", "--dataset", str(ds), "--output", str(raw_dir), "--limit", str(a.cases), "--max-seconds", "1800",
        *adapter(a.strategy, "raw"))

    g, r = rows(gov_dir), rows(raw_dir)
    common = sorted(set(g) & set(r))
    cap = {cid: g[cid]["benchmarks"]["cash_baseline_final_pence"] for cid in common}
    d_ret = np.array([(g[c]["output"]["final_cash_pence"] - r[c]["output"]["final_cash_pence"]) / cap[c] for c in common])
    d_dd = np.array([(g[c]["output"]["max_drawdown_bps"] - r[c]["output"]["max_drawdown_bps"]) / 1e4 for c in common])
    rng = np.random.default_rng(0)
    boot = lambda x: [float(np.quantile([x[rng.integers(len(x), size=len(x))].mean() for _ in range(4000)], q)) for q in (.05, .95)]
    gov_summary = json.loads((gov_dir / "summary.json").read_text())
    paired = {
        "pack": a.pack, "strategy": a.strategy, "paths_paired": len(common),
        "same_cases_check": "raw replay rebuilt from the revealed challenge seed; case ids match" if len(common) == len(g) else "PARTIAL MATCH",
        "governed_minus_raw_return": {"mean": float(d_ret.mean()), "ci90": boot(d_ret)},
        "governed_minus_raw_max_drawdown": {"mean": float(d_dd.mean()), "ci90": boot(d_dd)},
        "governed_better": int((d_ret > 0).sum()), "raw_better": int((d_ret < 0).sum()), "identical": int((d_ret == 0).sum()),
        "challenge_market_stats_governed": gov_summary.get("market_summary"),
        "challenge_commitment": (gov_dir / "COMMITMENT.txt").read_text().strip(),
        "provenance_warnings": gov_summary.get("challenge", {}).get("provenance", {}).get("warnings"),
    }
    (base / "paired.json").write_text(json.dumps(paired, indent=2))
    print(json.dumps(paired, indent=2))


if __name__ == "__main__":
    main()
