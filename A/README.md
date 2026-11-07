# Lane A — quant / data

The ready run is `binance-spot-btcusdt-1h-202411-202610`: Binance spot BTCUSDT hourly bars from 2024-11-01 through 2026-10-31, plus the Alternative.me Fear & Greed index. Refresh it with `scripts/fetch_snapshot.py`. Tests that need a planted price spike still use the seeded series `synthetic-btcusdt-1h-v1`.

A gate only multiplies a strategy's target position by 0, 0.5, or 1.

## What is real, and what is not

| Piece | Ready run |
|---|---|
| Prices, volume | Real Binance spot klines. 17,520 bars, no missing hours. |
| 24h and 7d momentum, 7d realised vol, 14-bar ATR, 7d price drawdown, volume z-score | Computed from those bars. Row t uses bars up to t. |
| Fear & Greed | Real Alternative.me daily index. Usable only from the next UTC day, because the historical publication time is not documented. |
| News | Omitted. The column is entirely missing. Nothing is filled in. |
| The two strategies | Demo generators (24/72 trend, 48-bar mean reversion) run on these prices. Not an imported live strategy, and not claimed as alpha. |
| Simple rule | Full size only when lagged momentum is positive and 7d vol is at or below the train median. Otherwise allocation is 0. |
| Verdict | Deterministic arbiter on the sealed test. An interval that still contains zero is INCONCLUSIVE. A drawdown above 40% cannot be overruled into keep or conditional activation. |
| 14-day paper plan | Recorded with the experiment. `completed` and `approved` are false. It is not a shadow-run result. |
| Fills | Real next-bar opens from the klines. PnL is that open to the following open. |
| Fees and slippage | Assumed: 10 bps Binance spot regular-user taker fee, plus 1 bp slippage. Not a measured fill. |
| Regimes, splits, Sharpe, drawdown, block-bootstrap intervals | Computed. Cutpoints are fit on the train window only. |
| LightGBM gate | Fit on train rows where the strategy is in the market, calibrated on validation. The last 2 bars of each of those windows are embargoed, because the label reaches into the next split. It never fits on the test window. |
| Walk-forward | Four expanding folds inside train only. They do not choose the sealed-test policy. |
| 14-day range | A block-bootstrap range from training returns, stored on the unstarted paper plan. A later result inside it is a plausible draw, not proof the strategy broke. |
| Fee check | Always-on on validation at half, one, and double the assumed cost. The arbiter does not read it. |
| Holdout | The last 20% of the real timeline. `run_experiment` scores the four pre-registered policies there once. `GateRunner.evaluate` refuses that split. |

The synthetic series is still in the package so the fill, leakage, and cost tests can force a close spike. It is not what `scripts/run_experiment.py` runs.

## Run

```bash
cd A
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/python scripts/run_experiment.py
```

LightGBM needs `libomp` (`brew install libomp` on macOS).

```python
from kok_a import run_experiment

result = run_experiment("btc-trend-24-72-demo", "binance-spot-btcusdt-1h-202411-202610")
```

`result.provenance` says which inputs were measured and which were assumed. The other demo strategy is `btc-meanrev-48-demo`.
