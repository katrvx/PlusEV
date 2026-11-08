# Lane A — quant / data

The sealed-test snapshot is `binance-spot-btcusdt-1h-201802-202610`: Binance spot BTCUSDT hourly bars from 2018-02-01 through 2026-10-31, 76,559 bars with 26 real Binance gaps, plus the Alternative.me Fear & Greed index from 2018-02-01 (3,191 rows). Refresh it with `scripts/fetch_snapshot.py`.

A separate series, `binance-spot-btcusdt-5m-202605-202611`, is spot BTCUSDT 5-minute bars from 2026-05-08 through 2026-11-07 23:55 UTC: 52,992 bars and no gaps. It is stored in `fixtures/btcusdt_5m_spot.csv`. It is not the sealed-test snapshot. The 24/72 and 48 counts are hourly bars.

The 24/72 trend, the 48-bar mean reversion, and the cost (10 bp fee + 1 bp slippage) were fixed before this run. They were not retuned on the longer window.

After the feature warmup, the chronological 60/20/20 cuts on the hourly snapshot are train 2018-02-08 01:00 through 2023-05-07 18:00, validation 2023-05-07 19:00 through 2025-02-02 08:00, and test 2025-02-02 09:00 through 2026-10-31 22:00.

The sealed-test look on that snapshot, 2,000 bootstrap draws, run on 2026-11-08:

- `btc-trend-24-72-demo` (`trend-sma-24-72-v1`): **INCONCLUSIVE**, policy `always_on`. The sealed-test intervals still contain zero.
- `btc-meanrev-48-demo` (`meanrev-z48-v1`): **KILL**, policy `cash`. Always-on drawdown 60.4% exceeds the 40% cap, and the interval on its net return is entirely below zero.

`synthetic-btcusdt-1h-v1` is the control, not the demo. Calm stretches carry a planted drift, and a close spike is not the fill. The arbiter checks are the power and false-positive control: an interval that contains zero is INCONCLUSIVE, a gate whose interval sits entirely above zero is selected, and always-on entirely below zero past the 40% drawdown cap is KILL.

A gate only multiplies a strategy's target position by 0, 0.5, or 1.

## What is real, and what is not

| Piece | Ready run |
|---|---|
| Prices, volume | Real Binance spot klines. 76,559 hourly bars. 26 gaps are missing hours on the exchange; successive rows are still the next fill. |
| 24h and 7d momentum, 7d realised vol, 14-bar ATR, 7d price drawdown, volume z-score | Computed from those bars. Row t uses bars up to t. |
| Fear & Greed | Real Alternative.me daily index. Usable only from the next UTC day, because the historical publication time is not documented. |
| News | Omitted. The column is entirely missing. Nothing is filled in. |
| The two strategies | Demo generators (24/72 trend, 48-bar mean reversion) run on these prices. Not an imported live strategy, and not claimed as alpha. |
| Simple rule | Full size only when lagged momentum is positive and 7d vol is at or below the train median. Otherwise allocation is 0. This is the fixed baseline. |
| Regime filter | Chosen on train from the buckets whose return interval sits entirely above or below zero: trend, volatility, liquidity, and sentiment when that column is actually populated. News is skipped while it is missing. The sealed test only scores the frozen filter. |
| Verdict | Deterministic arbiter on the sealed test. An interval that still contains zero is INCONCLUSIVE. A drawdown above 40% cannot be overruled into keep or conditional activation. |
| 14-day paper plan | Recorded with the experiment. `completed` and `approved` are false. It is not a shadow-run result. |
| Fills | Real next-bar opens from the klines. PnL is that open to the following open. |
| Fees and slippage | Assumed: 10 bps Binance spot regular-user taker fee, plus 1 bp slippage. Not a measured fill. |
| Regimes, splits, Sharpe, drawdown, block-bootstrap intervals | Computed. Cutpoints are fit on the train window only. |
| LightGBM gate | Fit on the early in-market train rows, calibrated on the last 25% of those rows. The allocation band is that tail's base rate ± 2 points, fixed before validation. It is not the old 0.45/0.55 cut. `spec()` includes the seed, the band, and a hash of the fitted model. It never fits on the test window. |
| Walk-forward | Four expanding folds inside train only. `GateRunner.evaluate_folds` scores any frozen spec on those same windows. They do not choose the sealed-test policy. If the LightGBM gate loses on every scored fold, that loss is written into the run notes. |
| 14-day range | A block-bootstrap range from training returns, stored on the unstarted paper plan. A later result inside it is a plausible draw, not proof the strategy broke. |
| Fee check | Always-on on validation at half, one, and double the assumed cost. The arbiter does not read it. |
| Holdout | The last 20% of the real timeline. `run_experiment` scores the pre-registered policies there once. `GateRunner.evaluate` refuses that split. |

The synthetic series stays in the package for the fill, leakage, cost, and arbiter checks. `scripts/run_experiment.py` runs the hourly Binance snapshot.

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

result = run_experiment("btc-trend-24-72-demo", "binance-spot-btcusdt-1h-201802-202610")
```

`result.provenance` says which inputs were measured and which were assumed. The other demo strategy is `btc-meanrev-48-demo`.
