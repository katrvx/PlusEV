# Lane A → Lane B

The ready book is hourly again. Snapshot id: `binance-spot-btcusdt-1h-201802-202610`. Spot BTCUSDT, 2018-02-01 through 2026-10-31, 76,559 bars, 26 real Binance gaps. Fear & Greed is the same Alternative.me series from 2018-02-01. `load_for_lane_b("")` and `load_for_lane_b("btc-trend-24-72-demo")` already point at that id. `btc-meanrev-48-demo` does too.

The 5-minute file `A/fixtures/btcusdt_5m_spot.csv` is not this rail. Do not load it.

## What to rerun

The two checked-in Argon reports are the old window, November 2024–October 2026. Validation there was about 99% fear. On this book the cuts, after feature warmup, are:

- train 2018-02-08 01:00 → 2023-05-07 18:00
- validation 2023-05-07 19:00 → 2025-02-02 08:00
- test 2025-02-02 09:00 → 2026-10-31 22:00

Please rerun both investigations on this snapshot. A full Lane A assemble with 2,000 bootstrap draws is a few minutes per strategy before the agents start.

```bash
python3 scripts/run_investigation.py --lane-a
python3 scripts/run_investigation.py --lane-a --experiment-id btc-meanrev-48-demo
```

`--fallback` still works if you want the deterministic agents first. `--frozen` is still the one sealed look, and only for a champion your arbiter accepted.

## What you do not need to change

- Strategy parameters stay 24/72 and 48. Cost stays 10 bp plus 1 bp. They were fixed before the longer run.
- A 14-day block is still 336 hourly bars. `health.py` dividing `horizon_bars` by 24 is still right.
- `load_for_lane_b` still returns train and validation only. The test dates stay so a news window that crosses the holdout is still refused. `decision` and `paper_plan` are still null. The note that quotes the sealed verdict (`Verdict … comes from the deterministic arbiter`) is dropped in that view. `redact` still clears every note.
- Your verdict words stay `candidate_for_frozen_test` or `INCONCLUSIVE`. Lane A's arbiter is separate. On this book it already said: trend `btc-trend-24-72-demo` **INCONCLUSIVE** via `always_on` (the sealed intervals still contain zero); mean reversion `btc-meanrev-48-demo` **KILL** via `cash` (always-on drawdown 60.4% past the 40% cap, and its net-return interval is entirely below zero). Those are in `A/README.md`. They are not a substitute for your rerun.
- News is still omitted. Coverage of `news_sentiment` is 0. There is no first-seen archive on this snapshot.
- Funding is still zero because the venue is spot.

## Fields that now exist, and what happens if you ignore them

Lane A's `Metrics` now always carries `cvar_05` and `avg_holding_bars` (average consecutive hours in the market). Your `packages/contracts_lane_b.Metrics` does not list them. Pydantic drops unknown fields if you re-parse a dump through that model. The live objects from `load_for_lane_b` keep them, and `evaluation.model_dump()` inside your tools will include them in evidence. You can cite them. You do not have to add the fields to your contract to rerun.

The 14-day shadow log is Lane A's paper plan, after a person approves. It is not on the development view. An empty log is not a result: the stored book ends at 2026-10-31 23:00 UTC, so no hour has been logged yet. A finished 336-bar path inside the training range is `INCONCLUSIVE`. A finished path outside it is `MONITOR`. It does not retune the sealed test and it does not replace your critic.

Sortino was already on your `Metrics`. The API comparison table now also shows Sortino, 5% CVaR, and holding time. That is the Part C presentation, not a new tool.
