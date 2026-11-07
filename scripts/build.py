"""Build everything the MVP shows, from any finance-kit dataset folders.

    python3 scripts/build.py                                   # synthetic kit data (offline)
    python3 scripts/build.py --train data/real-train --holdout data/real-holdout --dev data/real-dev

Dataset folders are produced by the kit:
    bench.py generate --pack markets --cases 600 --seed 101 --output data/kit-train   (synthetic, offline)
    bench.py fetch    --cases 400    --seed 101 --output data/real-train              (real Binance, needs internet)

Steps:
  1. fit regime thresholds on TRAIN only, freeze them
  2. run each base strategy on TRAIN and HOLDOUT -> trades tagged with regimes
  3. X-ray: per-regime tests on TRAIN, BH correction, confirm on HOLDOUT -> frozen envelope
  4. on DEV (never used to build anything): raw strategy vs governed vs buy-and-hold
  5. Kill-or-Keep demo streams: an alive strategy and one whose edge dies at a hidden trade T
Only inputs.jsonl is read; the evaluator-side files are never opened.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from plusev import judge, regime as rg  # noqa: E402
from plusev.execution import buy_and_hold, simulate, strategy_decider  # noqa: E402
from plusev.governor import Governor  # noqa: E402
from plusev.strategies import STRATEGIES  # noqa: E402


def load_cases(folder: Path) -> list[dict]:
    rows = [json.loads(l) for l in (folder / "inputs.jsonl").read_text().splitlines() if l.strip()]
    return [{"case_id": r["case_id"], **r["input"]} for r in rows if r.get("task") == "markets"]


def run_strategy(cases, decide, thr):
    trades, sims = [], []
    for c in cases:
        s = simulate(c, decide, thr, path_id=c["case_id"])
        trades += s["trades"]
        sims.append(s)
    return trades, sims


def noise_decider(seed: int):
    """Zero-edge strategy: random entries/exits, deterministic per path and bar."""
    def decide(prices, shares):
        h = hashlib.sha256(f"{seed}:{len(prices)}:{prices[0]}:{prices[-1]}".encode()).digest()[0] / 255
        if shares == 0 and h < 0.15:
            return "buy", "noise entry"
        if shares > 0 and h < 0.25:
            return "sell", "noise exit"
        return "hold", "noise"
    return decide


def git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, default=ROOT / "data/kit-train")
    ap.add_argument("--holdout", type=Path, default=ROOT / "data/kit-holdout")
    ap.add_argument("--dev", type=Path, default=ROOT / "data/kit-dev")
    ap.add_argument("--label", default="synthetic kit `markets` pack (practice data, not a hidden-test result)")
    args = ap.parse_args()

    train, holdout, dev = load_cases(args.train), load_cases(args.holdout), load_cases(args.dev)
    print(f"paths: train {len(train)}, holdout {len(holdout)}, dev {len(dev)}", file=sys.stderr)

    thr = rg.fit_thresholds([c["prices_pence"] for c in train])
    rg.save(thr, ROOT / "envelopes/regime_thresholds.json")

    out = ROOT / "eval/mvp"
    out.mkdir(parents=True, exist_ok=True)
    summary = {"data": args.label, "commit": git_head(), "paths": {"train": len(train), "holdout": len(holdout), "dev": len(dev)}, "strategies": {}}

    for name, strat in STRATEGIES.items():
        decide = strategy_decider(strat)
        tr_train, _ = run_strategy(train, decide, thr)
        tr_hold, _ = run_strategy(holdout, decide, thr)
        env = judge.xray(name, tr_train, tr_hold, trained_on=f"{args.train.name} + holdout {args.holdout.name} @ {git_head()}")
        judge.save_envelope(env, ROOT / f"envelopes/{name}.json")

        gov = Governor(strat, env, thr)
        rows = []
        for c in dev:
            raw = simulate(c, decide, thr, c["case_id"])
            gvd = simulate(c, gov.decide, thr, c["case_id"])
            bh = buy_and_hold(c)
            cap = c["initial_cash_pence"]
            rows.append({
                "case_id": c["case_id"],
                "raw_ret": raw["profit_pence"] / cap, "gov_ret": gvd["profit_pence"] / cap, "bh_ret": (bh - cap) / cap,
                "raw_dd": raw["max_drawdown"], "gov_dd": gvd["max_drawdown"],
                "raw_trades": len(raw["trades"]), "gov_trades": len(gvd["trades"]),
                "blocked": sum(d["reason"].startswith(("BLOCKED", "EXIT")) for d in gvd["decisions"]),
            })
        diff = np.array([r["gov_ret"] - r["raw_ret"] for r in rows])
        rng = np.random.default_rng(3)
        boots = [diff[rng.integers(len(diff), size=len(diff))].mean() for _ in range(2000)]
        dd_diff = np.array([r["gov_dd"] - r["raw_dd"] for r in rows])
        dd_boots = [dd_diff[rng.integers(len(dd_diff), size=len(dd_diff))].mean() for _ in range(2000)]
        changed = [r for r in rows if r["blocked"]]
        summary["strategies"][name] = {
            "train_trades": len(tr_train), "holdout_trades": len(tr_hold),
            "proposed": env["hypotheses_proposed"], "survived_training": env["survived_training"], "confirmed_holdout": env["confirmed_holdout"],
            "red": [f'{b["feature"]}={b["bucket"]}' for b in env["buckets"] if b["status"] == "red"],
            "green": [f'{b["feature"]}={b["bucket"]}' for b in env["buckets"] if b["status"] == "green"],
            "dev_mean_return": {"raw": float(np.mean([r["raw_ret"] for r in rows])), "governed": float(np.mean([r["gov_ret"] for r in rows])), "buy_and_hold": float(np.mean([r["bh_ret"] for r in rows]))},
            "dev_mean_drawdown": {"raw": float(np.mean([r["raw_dd"] for r in rows])), "governed": float(np.mean([r["gov_dd"] for r in rows]))},
            "governed_minus_raw_return": {"mean": float(diff.mean()), "ci90": [float(np.quantile(boots, .05)), float(np.quantile(boots, .95))]},
            "governed_minus_raw_drawdown": {"mean": float(dd_diff.mean()), "ci90": [float(np.quantile(dd_boots, .05)), float(np.quantile(dd_boots, .95))]},
            "paths_changed_by_governor": len(changed),
            "wins_vs_raw": int((diff > 0).sum()), "losses_vs_raw": int((diff < 0).sum()),
        }
        (out / f"dev_{name}.json").write_text(json.dumps(rows))

        # Kill-or-Keep demo: chain dev paths into one long "live" stream of trades
        tr_dev, _ = run_strategy(dev, decide, thr)
        tr_noise, _ = run_strategy(dev, noise_decider(5), thr)
        T = len(tr_dev) // 3
        rnd = random.Random(9)
        dying = tr_dev[:T] + rnd.sample(tr_noise, min(len(tr_noise), len(tr_dev) - T))
        streams = {"alive": tr_dev, "dying": dying}
        kk = {"T_hidden": T, "streams": {}}
        for sname, stream in streams.items():
            checkpoints = sorted({min(len(stream), k) for k in (10, 20, 40, 60, 80, 120, 160, 200, 300, len(stream))})
            kk["streams"][sname] = {
                "returns": [t["net_return"] for t in stream],
                "verdicts": {k: {kk_k: v for kk_k, v in judge.kill_or_keep(tr_train, stream[:k]).items()} for k in checkpoints},
            }
        (out / f"killorkeep_{name}.json").write_text(json.dumps(kk))

        s = summary["strategies"][name]
        print(f"{name:15s} trades {len(tr_train):4d}/{len(tr_hold):4d}  proposed {s['proposed']}  BH {s['survived_training']}  confirmed {s['confirmed_holdout']}  "
              f"red {s['red']}  dev ret raw {s['dev_mean_return']['raw']:+.4f} gov {s['dev_mean_return']['governed']:+.4f}  "
              f"dd raw {s['dev_mean_drawdown']['raw']:.4f} gov {s['dev_mean_drawdown']['governed']:.4f}", file=sys.stderr)

    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"wrote {out}/summary.json", file=sys.stderr)


if __name__ == "__main__":
    main()
