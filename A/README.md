# Lane A

Quant and data for Keep or Kill. The package is [`kok_a`](kok_a/__init__.py). It does not rewrite a strategy. It joins point-in-time context, simulates a 0 / 0.5 / 1 allocation on the next bar's open, and returns a sealed verdict.

## Contents

- [Layout](#layout)
- [Book](#book)
- [Strategies and cost](#strategies-and-cost)
- [Splits](#splits)
- [Engine](#engine)
- [Train gate and validation benchmarks](#train-gate-and-validation-benchmarks)
- [Sealed results](#sealed-results)
- [Run](#run)

## Layout

| Path | What |
|---|---|
| [`kok_a/__init__.py`](kok_a/__init__.py) | Public entry: `run_experiment`, `load_for_lane_b` |
| [`kok_a/snapshot.py`](kok_a/snapshot.py) | Hourly book, Fear & Greed, separate 5-minute series |
| [`kok_a/binance.py`](kok_a/binance.py) | Kline time normalisation |
| [`kok_a/features.py`](kok_a/features.py) | Point-in-time features and the as-of join |
| [`kok_a/strategies.py`](kok_a/strategies.py) | The two frozen position generators |
| [`kok_a/simulate.py`](kok_a/simulate.py) | Next-bar fills, fees, slippage |
| [`kok_a/gates.py`](kok_a/gates.py) | Threshold rule and regime-filter allocation |
| [`kok_a/lgbm_gate.py`](kok_a/lgbm_gate.py) | LightGBM gate |
| [`kok_a/regimes.py`](kok_a/regimes.py) | Train-fit regime labels and the regime filter |
| [`kok_a/experiment.py`](kok_a/experiment.py) | Splits, walk-forward, metrics, `GateRunner` |
| [`kok_a/arbiter.py`](kok_a/arbiter.py) | Deterministic verdict and the paper plan |
| [`kok_a/paper.py`](kok_a/paper.py) | 14-day shadow log |
| [`kok_a/contracts.py`](kok_a/contracts.py) | Result types Lane B reads |
| [`fixtures/`](fixtures/) | Checked-in hourly book, Fear & Greed, 5-minute series |
| [`tests/test_lane_a.py`](tests/test_lane_a.py) | Leakage, fills, costs, holdout, arbiter |
| [`scripts/fetch_snapshot.py`](scripts/fetch_snapshot.py) | Refresh the checked-in book |
| [`scripts/run_experiment.py`](scripts/run_experiment.py) | Run the hourly snapshot |

## Book

Hourly spot BTCUSDT, id `binance-spot-btcusdt-1h-201802-202610`, defined in [`snapshot.py`](kok_a/snapshot.py).

- Prices: [`fixtures/btcusdt_1h_spot.csv`](fixtures/btcusdt_1h_spot.csv). 2018-02-01 through 2026-10-31, 76,559 bars, 26 missing hours.
- Fear & Greed: [`fixtures/fear_greed.csv`](fixtures/fear_greed.csv). Alternative.me, 3,191 rows from 2018-02-01, usable the next UTC day. Join is [`asof_fear_greed`](kok_a/features.py).
- News: no column. Nothing is filled in.
- Funding: zero. The book is spot.

[`fixtures/btcusdt_5m_spot.csv`](fixtures/btcusdt_5m_spot.csv) is six months of 5-minute bars (`binance-spot-btcusdt-5m-202605-202611`, 52,992 bars). It is not the sealed snapshot. The 24, 72, and 48 counts are hourly bars.

## Strategies and cost

Defined in [`strategies.py`](kok_a/strategies.py). These are generators on the book above, not imported live strategies.

| Id | Rule |
|---|---|
| `btc-trend-24-72-demo` (`trend-sma-24-72-v1`) | Long when the 24-bar average is above the 72-bar average |
| `btc-meanrev-48-demo` (`meanrev-z48-v1`) | Enter when the 48-bar z-score is below −1, exit at 0 |

[`simulate.py`](kok_a/simulate.py) charges 10 bp plus 1 bp. A gate, in [`gates.py`](kok_a/gates.py), only multiplies the target by 0, 0.5, or 1. The fill is the next bar's open.

## Splits

After feature warmup, from [`experiment.py`](kok_a/experiment.py):

| Split | Window |
|---|---|
| Train | 2018-02-08 01:00 through 2023-05-07 18:00 |
| Validation | 2023-05-07 19:00 through 2025-02-02 08:00 |
| Test | 2025-02-02 09:00 through 2026-10-31 22:00 |

The test is the last 20%. `GateRunner.evaluate` refuses it. `run_experiment` scores the pre-registered policies there once.

## Engine

| Piece | Where | What it is |
|---|---|---|
| Features | [`features.py`](kok_a/features.py) | 24h and 7d momentum, 7d realised vol, 24h vol divided by that 7d vol, 14-bar ATR, 7d drawdown, volume z-score, Fear & Greed. Row t uses bars up to t. |
| Regimes | [`regimes.py`](kok_a/regimes.py) | 24h trend, 7d trend, vol level, vol versus its 7d baseline, volume, sentiment. Cutpoints fit on train only. The names are not a claim that bullish or calm is good. |
| Simple rule | [`gates.py`](kok_a/gates.py) | Full size only when lagged momentum is positive and 7d vol is at or below the train median. Otherwise 0. |
| Regime filter | [`regimes.py`](kok_a/regimes.py) | Train buckets whose bar-return interval sits entirely above zero get 1. Buckets entirely below zero get 0. A bar matching any full-size bucket is on, unless it also matches a flat bucket. |
| Exposure benchmarks | [`gates.py`](kok_a/gates.py) | Constant half-size, and a constant frozen to the gate's average train exposure. Lower drawdown alone is not the comparison. |
| LightGBM | [`lgbm_gate.py`](kok_a/lgbm_gate.py) | Fit on early in-market train rows. Calibrated on the last 25% of those rows. Band is that tail's base rate ± 2 points. |
| Walk-forward | [`experiment.py`](kok_a/experiment.py) | Four expanding folds inside train, 2-bar embargo. They do not pick the sealed policy. |
| Metrics | [`experiment.py`](kok_a/experiment.py) | Net return, Sharpe, Sortino, 5% CVaR, drawdown, exposure, turnover, average holding time. Block bootstrap, 2,000 draws. |
| Arbiter | [`arbiter.py`](kok_a/arbiter.py) | An interval that contains zero is `INCONCLUSIVE`. Drawdown above 40% cannot become a keep or a conditional activation. |
| Paper plan | [`paper.py`](kok_a/paper.py) | 336 hourly bars. Recorded, not started. The book ends at 2026-10-31 23:00 UTC, so the log has no fills. |
| Control | [`market.py`](kok_a/market.py) | `synthetic-btcusdt-1h-v1`, for fill, leakage, cost, and arbiter checks. Not the demo. |

## Train gate and validation benchmarks

The rule below is fit on train only, with 2,000 block-bootstrap draws, seed 7. Validation is the check. The sealed test was not used to choose it. No spread, order-book depth, or quoted-slippage history is in the book. `volume_zscore` is traded volume against its own 7-day baseline. Fear & Greed is the next-UTC-day index. News is absent.

A bucket is full size only when its train interval lies entirely above zero, and flat only when that interval lies entirely below zero. Every other bucket is left out of the rule.

Trend `btc-trend-24-72-demo`, full size when any of these is true, otherwise flat: 24h trend bull, 7d trend bull, 7d vol low, volume deep, Fear & Greed greed. No train bucket was entirely below zero. Vol-versus-baseline did not clear zero. On validation the gate's compounded net is +114.1% (drawdown 34.7%, exposure 0.55). Always-on is +134.4% at exposure 0.55. The train-matched constant (0.95) is +125.1%. Half-size is +57.0%. The simple rule is −25.6%. The gate does not beat staying on, or staying on at the same average size.

Mean reversion `btc-meanrev-48-demo`, flat when any of these is true, otherwise full size: 24h trend bull, 7d trend sideways, 7d vol low. No train bucket was entirely above zero. Volume, vol-change, and sentiment did not clear zero. On validation the gate's compounded net is +38.8% (drawdown 12.0%, exposure 0.03). Always-on is −19.5% at exposure 0.35. Half-size is −8.4%. The train-matched constant (0.36) is −5.7% at exposure 0.13. Cash is 0. The simple rule is −40.7%. The gate's validation exposure is lower than that frozen constant, because those flat conditions cover more of validation than of train.

Lane B still chooses its own gate from `packages/research_agents/allowlist.py`. `vol_ratio_24h_7d` is on this frame and is not in that allowlist.

## Sealed results

Hourly book, 2026-11-08. Produced by [`decide`](kok_a/arbiter.py).

| Strategy | Verdict | Policy | Why |
|---|---|---|---|
| Trend | INCONCLUSIVE | `always_on` | The intervals contain zero |
| Mean reversion | KILL | `cash` | Always-on drawdown is 60.4%, past the 40% cap, and its net-return interval is entirely below zero |

The later mean-reversion champion's one sealed look is not this call. It is [`experiments/frozen_look_btc-meanrev-48-demo.json`](../experiments/frozen_look_btc-meanrev-48-demo.json).

## Run

From `A/`, with `libomp` installed (`brew install libomp` on macOS):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/python scripts/run_experiment.py
```

```python
from kok_a import run_experiment

result = run_experiment("btc-trend-24-72-demo", "binance-spot-btcusdt-1h-201802-202610")
```

`result.provenance` names what was measured and what was assumed. The other strategy id is `btc-meanrev-48-demo`. Lane B's development view is `load_for_lane_b` in the same module.
