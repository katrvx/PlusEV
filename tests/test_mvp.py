"""Core guarantees of the MVP. Run: python3 -m pytest -q  (or python3 tests/test_mvp.py)"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from plusev import judge, regime as rg


def test_regime_has_no_lookahead():
    rnd = random.Random(1)
    prices = [10000]
    for _ in range(60):
        prices.append(max(1, int(prices[-1] * (1 + rnd.gauss(0, 0.02)))))
    thr = rg.fit_thresholds([prices])
    for t in range(rg.WARMUP, 50):
        before = rg.regime_at(prices[: t + 1], t, thr)
        garbage = prices[: t + 1] + [1, 10**9, 5] * 5
        assert rg.regime_at(garbage, t, thr) == before


def test_bh_controls_false_discoveries_on_noise():
    rng = np.random.default_rng(0)
    false_hits = 0
    for seed in range(30):
        trades = [{"net_return": float(rng.normal(0, 0.01)),
                   "regime": {"vol": rng.choice(["low", "mid", "high"]), "shock": rng.choice(["calm", "shock"]),
                              "trend": rng.choice(["up", "down", "chop"])}} for _ in range(150)]
        holdout = trades[:60]
        env = judge.xray("noise", trades, holdout, seed=seed)
        false_hits += env["confirmed_holdout"]
    assert false_hits / (30 * 8) <= judge.Q_FDR


def test_e_process_false_alarm_rate():
    rng = np.random.default_rng(1)
    alarms = 0
    for _ in range(500):
        e = judge.BettingEProcess()
        for y in rng.uniform(-1, 1, 200):  # mean exactly 0: H0 true
            if e.update(float(y)) >= 1 / judge.ALPHA:
                alarms += 1
                break
    assert alarms / 500 <= judge.ALPHA


if __name__ == "__main__":
    test_regime_has_no_lookahead()
    test_bh_controls_false_discoveries_on_noise()
    test_e_process_false_alarm_rate()
    print("all MVP tests pass")
