"""Keep or Kill hidden-challenge evidence with a paired raw baseline.

Pre-registration: eval/challenge/kok-preregistration.md (rule, parameters, comparison).

Step 1 (claimable result): the organisers' `challenge` with the GATED adapter.
Fresh secret seed, cases only in memory, commitment written before the run.

    python3 scripts/kok_challenge.py challenge --strategy mean_reversion

Step 2 (paired baseline): after the run the kit publishes the seed in the challenge
folder. Pass it explicitly (this script never opens seed files); the same cases are
rebuilt with the kit's `generate` and the RAW adapter is run on them with the kit's
`run`, so gated vs raw is compared path by path on identical hidden paths.

    python3 scripts/kok_challenge.py replay --strategy mean_reversion --seed <revealed seed>

Writes eval/challenge/kok-<strategy>/{gated/, raw-replay/, revealed-cases/, paired.json}.

Practice (protocol debugging only, not a result): `practice --seed N --base <scratch dir>`
runs the gated adapter with the kit's `run` on generated cases, then the same replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from packages.kit_adapter import rule, sim  # noqa: E402

KIT = ROOT / "agentverse" / "finance" / "bench.py"
PACK, CASES, MAX_SECONDS = "markets", 300, "1800"
ADAPTER_FILES = ("packages/kit_adapter/kok.py", "packages/kit_adapter/rule.py", "A/kok_a/strategies.py")


def kit(*args: str, log: Path | None = None) -> int:
    done = subprocess.run([sys.executable, str(KIT), *args], cwd=ROOT, capture_output=True, text=True)
    if log is not None:
        log.write_text(f"exit code {done.returncode}\n--- stdout ---\n{done.stdout}\n--- stderr ---\n{done.stderr}")
    if done.returncode not in (0, 1):  # 1 = run finished but reported errors / not-run cases
        sys.exit(f"kit {args[0]} failed ({done.returncode}): {done.stderr[-2000:]}")
    return done.returncode


def adapter(strategy: str, mode: str) -> list[str]:
    return ["--adapter", sys.executable, "-m", "packages.kit_adapter.kok", "--strategy", strategy, "--mode", mode]


def rows(folder: Path) -> dict:
    out = {}
    for line in (folder / "case-results.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r.get("status") == "simulated":
            out[r["case_id"]] = r
    return out


def sign_test_p(wins: int, losses: int) -> float | None:
    """Two-sided exact binomial test (ties excluded), same formula as the kit's."""
    n = wins + losses
    if not n:
        return None
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2**n)


def boot_ci(x: np.ndarray, seed: int = 0) -> list[float] | None:
    if not len(x):
        return None
    rng = np.random.default_rng(seed)
    means = [x[rng.integers(len(x), size=len(x))].mean() for _ in range(4000)]
    return [float(np.quantile(means, 0.05)), float(np.quantile(means, 0.95))]


def compare(a: dict, b: dict, ids: list[str], start: dict) -> dict:
    """a minus b, paired by case id. a/b: id -> {final_cash_pence, max_drawdown_bps}."""
    fa = np.array([a[c]["final_cash_pence"] for c in ids], dtype=float)
    fb = np.array([b[c]["final_cash_pence"] for c in ids], dtype=float)
    cap = np.array([start[c] for c in ids], dtype=float)
    d_ret = (fa - fb) / cap
    d_dd = np.array([a[c]["max_drawdown_bps"] - b[c]["max_drawdown_bps"] for c in ids], dtype=float) / 1e4
    better, worse = int((fa > fb).sum()), int((fa < fb).sum())
    diff = fa != fb
    return {
        "paths_paired": len(ids),
        "a_better": better,
        "b_better": worse,
        "identical": int((~diff).sum()),
        "sign_test_p_two_sided": sign_test_p(better, worse),
        "return_diff_all_paths": {"mean": float(d_ret.mean()), "median": float(np.median(d_ret)), "ci90_mean": boot_ci(d_ret)},
        "return_diff_non_identical": {"n": int(diff.sum()), "mean": float(d_ret[diff].mean()) if diff.any() else None,
                                      "median": float(np.median(d_ret[diff])) if diff.any() else None},
        "max_drawdown_diff_all_paths": {"mean": float(d_dd.mean()), "median": float(np.median(d_dd)), "ci90_mean": boot_ci(d_dd)},
        "max_drawdown_diff_non_identical": {"mean": float(d_dd[diff].mean()) if diff.any() else None,
                                            "median": float(np.median(d_dd[diff])) if diff.any() else None},
    }


def rename(c: dict, a: str, b: str) -> dict:
    return {k.replace("a_better", f"{a}_better").replace("b_better", f"{b}_better"): v for k, v in c.items()}


def replay(strategy: str, seed: int, base: Path, cases: int) -> dict:
    gated_dir, raw_dir, ds = base / "gated", base / "raw-replay", base / "revealed-cases"
    kit("generate", "--pack", PACK, "--cases", str(cases), "--seed", str(seed), "--output", str(ds))
    kit("run", "--dataset", str(ds), "--output", str(raw_dir), "--limit", str(cases), "--max-seconds", MAX_SECONDS,
        *adapter(strategy, "raw"), log=base / "raw-replay-kit-output.txt")

    g, r = rows(gated_dir), rows(raw_dir)
    ids = sorted(set(g) & set(r))
    same = all(g[c]["benchmarks"] == r[c]["benchmarks"] and g[c]["family"] == r[c]["family"] for c in ids)
    inputs = {}
    for line in (ds / "inputs.jsonl").read_text().splitlines():
        row = json.loads(line)
        inputs[row["case_id"]] = row["input"]
    start = {c: inputs[c]["initial_cash_pence"] for c in ids}
    kit_g = {c: g[c]["output"] for c in ids}
    kit_r = {c: r[c]["output"] for c in ids}
    cash = {c: {"final_cash_pence": start[c], "max_drawdown_bps": 0} for c in ids}

    # Offline replays of the same cases (our simulator; kit mode cross-checked against the kit).
    off = {}
    for name, mode, execution in (("raw_kit", "raw", "kit"), ("gated_kit", "gated", "kit"),
                                  ("raw_frac", "raw", "fractional"), ("gated_frac", "gated", "fractional"),
                                  ("half_frac", "half", "fractional")):
        fn = sim.target_fn(strategy, mode)
        off[name] = {c: sim.simulate(inputs[c], fn, execution) for c in ids}
    mismatch = [c for c in ids if off["gated_kit"][c]["final_cash_pence"] != kit_g[c]["final_cash_pence"]
                or off["raw_kit"][c]["final_cash_pence"] != kit_r[c]["final_cash_pence"]]

    def exposure(name: str) -> dict:
        bars = [x for c in ids for x in off[name][c]["exposure_bars"]]
        return {"mean_over_all_decision_bars": float(np.mean(bars)),
                "paths_with_any_exposure": sum(1 for c in ids if off[name][c]["mean_exposure"] > 0)}

    exp_raw, exp_gated = exposure("raw_kit"), exposure("gated_kit")
    raw_active = [c for c in ids if off["raw_kit"][c]["mean_exposure"] > 0]
    gated_summary = json.loads((gated_dir / "summary.json").read_text())
    raw_summary = json.loads((raw_dir / "summary.json").read_text())
    challenge_info = gated_summary.get("challenge") or {}
    commitment_file = gated_dir / "COMMITMENT.txt"

    paired = {
        "pack": PACK, "strategy": strategy, "strategy_id": rule.STRATEGY_IDS[strategy],
        "rule": "gated target = raw x (0.5 if 7-bar realized vol <= expanding median of earlier bars else 1.0); "
                "kit executes all-in long only when target = 1.0 (0.5 rounds down to flat)",
        "vol_window_bars": rule.VOL_WINDOW,
        "revealed_seed": seed,
        "paths_paired": len(ids),
        "same_cases_check": ("raw replay rebuilt from the revealed seed; all case ids, families and benchmarks match"
                             if same and len(ids) == len(g) == len(r) else
                             f"MISMATCH: gated {len(g)} raw {len(r)} common {len(ids)} same={same}"),
        "primary_kit_gated_vs_raw": rename(compare(kit_g, kit_r, ids, start), "gated", "raw"),
        "kit_market_verdict_gated_challenge": gated_summary.get("market_summary"),
        "kit_market_verdict_raw_replay (run, not challenge)": raw_summary.get("market_summary"),
        "exposure": {
            "definition": "fraction of equity held in the asset after each decision's fill, averaged over all decision bars "
                          "of all paths (offline kit-identical replay)",
            "raw": exp_raw, "gated": exp_gated,
            "gated_over_raw_ratio": (exp_gated["mean_over_all_decision_bars"] / exp_raw["mean_over_all_decision_bars"])
            if exp_raw["mean_over_all_decision_bars"] else None,
            "gated_over_raw_ratio_on_paths_where_raw_trades": (
                float(np.mean([off["gated_kit"][c]["mean_exposure"] for c in raw_active]) /
                      np.mean([off["raw_kit"][c]["mean_exposure"] for c in raw_active])) if raw_active else None),
            "paths_where_raw_trades": len(raw_active),
        },
        "offline_crosscheck_vs_kit": "offline kit-mode replay equals kit final cash on every path" if not mismatch
        else f"MISMATCH on {len(mismatch)} paths: {mismatch[:5]}",
        "exposure_only_baselines": {
            "in_kit_half_size_note": "half-size raw rounds to always-flat in the all-in kit, i.e. the cash baseline",
            "kit_gated_vs_cash": rename(compare(kit_g, cash, ids, start), "gated", "cash"),
            "kit_raw_vs_cash": rename(compare(kit_r, cash, ids, start), "raw", "cash"),
            "fractional_simulator_NOT_KIT": {
                "note": "our own integer-share simulator with the kit's fee/slippage/next-bar rules; 0.5 targets hold ~half",
                "gated_exact_vs_raw": rename(compare(off["gated_frac"], off["raw_frac"], ids, start), "gated", "raw"),
                "gated_exact_vs_half_size_raw": rename(compare(off["gated_frac"], off["half_frac"], ids, start), "gated", "half"),
                "half_size_raw_vs_raw": rename(compare(off["half_frac"], off["raw_frac"], ids, start), "half", "raw"),
                "mean_exposure": {k: float(np.mean([x for c in ids for x in off[k][c]["exposure_bars"]]))
                                  for k in ("raw_frac", "gated_frac", "half_frac")},
            },
        },
        "challenge_commitment": commitment_file.read_text().strip() if commitment_file.exists() else None,
        "challenge_kit_fingerprint": challenge_info.get("kit_fingerprint"),
        "provenance_warnings": (challenge_info.get("provenance") or {}).get("warnings"),
        "kit_errors": {"gated": gated_summary.get("errors"), "gated_not_run": gated_summary.get("not_run"),
                       "raw": raw_summary.get("errors"), "raw_not_run": raw_summary.get("not_run")},
        "adapter_source_sha256": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in ADAPTER_FILES},
    }
    (base / "paired.json").write_text(json.dumps(paired, indent=2) + "\n")
    return paired


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("challenge", "replay", "practice"))
    ap.add_argument("--strategy", choices=sorted(rule.STRATEGY_IDS), required=True)
    ap.add_argument("--seed", type=int, help="replay: the seed the kit revealed after the challenge; practice: any seed")
    ap.add_argument("--base", type=Path, help="practice only: scratch output folder (default: eval/challenge/kok-<strategy>)")
    ap.add_argument("--cases", type=int, default=CASES)
    a = ap.parse_args()

    if a.step == "practice":
        if a.base is None or a.seed is None:
            sys.exit("practice needs --base <scratch dir> and --seed")
        a.base.mkdir(parents=True, exist_ok=False)
        ds = a.base / "practice-cases"
        kit("generate", "--pack", PACK, "--cases", str(a.cases), "--seed", str(a.seed), "--output", str(ds))
        kit("run", "--dataset", str(ds), "--output", str(a.base / "gated"), "--limit", str(a.cases),
            "--max-seconds", MAX_SECONDS, *adapter(a.strategy, "gated"))
        print(json.dumps(replay(a.strategy, a.seed, a.base, a.cases), indent=2))
        return

    base = ROOT / "eval" / "challenge" / f"kok-{a.strategy}"
    if a.step == "challenge":
        if a.cases != CASES:
            sys.exit(f"pre-registered challenge size is {CASES} cases")
        base.mkdir(parents=True, exist_ok=False)
        code = kit("challenge", "--pack", PACK, "--cases", str(CASES), "--project", str(ROOT),
                   "--output", str(base / "gated"), "--max-seconds", MAX_SECONDS, *adapter(a.strategy, "gated"),
                   log=base / "challenge-kit-output.txt")
        print(f"challenge done (kit exit {code}): {base / 'gated'}. "
              "Now run the replay step with the seed the kit revealed in that folder.")
        return
    if a.seed is None:
        sys.exit("replay needs --seed (published by the kit in the challenge folder after the run)")
    print(json.dumps(replay(a.strategy, a.seed, base, CASES), indent=2))


if __name__ == "__main__":
    main()
