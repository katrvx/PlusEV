"""Fast checks for the Keep or Kill kit adapter (no challenge run)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from packages.kit_adapter import rule, sim

ROOT = Path(__file__).resolve().parent.parent


def path(seed: int, n: int = 80) -> list[int]:
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 0.03, n - 1) + np.where(np.arange(n - 1) < n // 2, -0.004, 0.006)
    return [max(200, int(p)) for p in 5000 * np.exp(np.concatenate([[0.0], np.cumsum(steps)]))]


def requests(prices: list[int], case_id: str = "synthetic"):
    shares = 0
    for t in range(len(prices) - 1):
        yield {"request_id": f"{case_id}:{t}", "case_id": case_id, "task": "market_step",
               "input": {"history": [{"date": f"d{i}", "price_pence": prices[i]} for i in range(t + 1)],
                         "cash_pence": 100000, "shares": shares, "fee_pence": 50, "slippage_bps": 10}}


@pytest.mark.parametrize("strategy,mode", [("mean_reversion", "gated"), ("trend", "raw")])
def test_adapter_speaks_jsonl_protocol(strategy, mode):
    prices = path(3)
    reqs = list(requests(prices)) + [{"request_id": "other", "task": "cashflow", "input": {}}]
    stdin = "".join(json.dumps(r) + "\n" for r in reqs)
    done = subprocess.run([sys.executable, "-m", "packages.kit_adapter.kok", "--strategy", strategy, "--mode", mode],
                          input=stdin, capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    assert len(lines) == len(reqs)  # exactly one stdout line per request, nothing else
    for req, line in zip(reqs, lines):
        resp = json.loads(line)
        assert resp["request_id"] == req["request_id"]
        if req["task"] == "market_step":
            assert resp["output"]["action"] in ("buy", "hold", "sell")
    assert json.loads(lines[-1])["output"] == {"error": "unsupported_task"}
    assert "kok adapter ready" in done.stderr


@pytest.mark.parametrize("strategy", sorted(rule.STRATEGY_IDS))
@pytest.mark.parametrize("seed", range(6))
def test_gated_uses_no_future_bars(strategy, seed):
    prices = path(seed)
    full = rule.target_positions(strategy, "gated", prices)
    gate = rule.gate_multipliers(prices)
    rng = np.random.default_rng(100 + seed)
    for k in (10, 30, 50, 73, 79):
        future = [int(p * rng.uniform(0.3, 3.0)) + 200 for p in prices[k:]]
        perturbed = prices[:k] + future
        assert np.array_equal(rule.target_positions(strategy, "gated", perturbed)[:k], full[:k])
        assert np.array_equal(rule.gate_multipliers(perturbed)[:k], gate[:k])
        assert np.array_equal(rule.target_positions(strategy, "gated", prices[:k]), full[:k])


@pytest.mark.parametrize("strategy", sorted(rule.STRATEGY_IDS))
@pytest.mark.parametrize("seed", range(6))
def test_gated_is_raw_times_half_or_full(strategy, seed):
    prices = path(seed)
    raw = rule.raw_positions(strategy, prices)
    gate = rule.gate_multipliers(prices)
    gated = rule.target_positions(strategy, "gated", prices)
    assert set(np.unique(raw)) <= {0.0, 1.0}
    assert set(np.unique(gate)) <= {0.5, 1.0}
    assert np.array_equal(gated, raw * gate)
    assert set(np.unique(gated)) <= {0.0, 0.5, 1.0}


def test_gate_matches_brute_force_expanding_median():
    prices = path(11)
    logret = np.diff(np.log(np.array(prices, dtype=float)))
    gate = rule.gate_multipliers(prices)
    vols = {}
    for t in range(len(prices)):
        if t >= 7:
            vols[t] = float(np.std(logret[t - 7:t], ddof=1))
        earlier = [vols[s] for s in range(7, t)]
        expected = 0.5 if t in vols and earlier and vols[t] <= np.median(earlier) else 1.0
        assert gate[t] == expected, t
    assert gate[:8].tolist() == [1.0] * 8  # warm-up: full size


def test_raw_is_the_frozen_demo_strategy():
    import importlib.util

    import pandas as pd

    spec = importlib.util.spec_from_file_location("frozen_check", ROOT / "A" / "kok_a" / "strategies.py")
    frozen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frozen)
    prices = path(5)
    for name, sid in rule.STRATEGY_IDS.items():
        _, expected = frozen.positions(sid, pd.Series(prices, dtype=float))
        assert np.array_equal(rule.raw_positions(name, prices), expected.fillna(0.0).to_numpy())


def test_half_target_executes_flat_in_all_in_kit():
    assert rule.kit_action(1.0, 0) == "buy"
    assert rule.kit_action(0.5, 0) == "hold"
    assert rule.kit_action(0.5, 10) == "sell"
    assert rule.kit_action(0.0, 10) == "sell"
    assert rule.kit_action(1.0, 10) == "hold"


def test_offline_sim_kit_mode_follows_adapter_actions():
    prices = path(2)
    data = {"prices_pence": prices, "initial_cash_pence": 500000, "fee_pence": 100, "slippage_bps": 20}
    full = sim.simulate(data, lambda p: 1.0)
    fill = (prices[1] * 10020 + 9999) // 10000
    units = (500000 - 100) // fill
    hold = 500000 - 100 - units * fill + units * (prices[-1] * 9980 // 10000) - 100
    assert full["final_cash_pence"] == hold  # always-long equals buy-and-hold accounting
    assert sim.simulate(data, lambda p: 0.0)["final_cash_pence"] == 500000
    half = sim.simulate(data, lambda p: 0.5, "fractional")
    assert 0.45 < half["mean_exposure"] < 0.55
