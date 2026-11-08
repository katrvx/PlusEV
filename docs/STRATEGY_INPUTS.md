# Strategy inputs

Keep / Kill verifies a strategy without asking its owner to reveal source code. The primary verification input is the strategy's timestamped positions, supplied as CSV/Parquet or through a platform API. A completed-trade export is a secondary diagnostic input; it cannot reconstruct the strategy or prove how it would behave in a new market.

## Current product flow

The demo is intentionally judgeable from the seeded example:

1. Open the example strategy.
2. Read the verdict and its plain-language reason.
3. Inspect where the result changes by market condition.
4. Follow the evidence and the native agent report.
5. Compare the supplied original, simple rule, proposed filter and cash series.
6. Review or save a paper plan. Plans are saved protocols, not running tests.

For a user's strategy, **Verify a strategy** opens the positions path. The user can name the strategy, map timestamps/symbol/allocation, set costs and timezone, and save the positions as a separate research input. The importer does not infer rules from rows and does not attach history to a different strategy definition. Strategy source code stays private.

The optional rule builder / strategy-definition JSON path is retained as a draft-only capability. It stores a bounded, inspectable rule definition, but it does not generate positions, attach market data, run an evaluator, or produce metrics. The existing import, experiment, evidence, report and paper-plan contracts remain the source of truth.

The optional draft builder supports two declarative rule families:

- `ema_crossover`: after warmup, use closed-bar prices and target long position `1` when the fast EMA is above the slow EMA; otherwise target flat position `0`.
- `rsi_mean_reversion`: use a closed-bar RSI, enter long at `1` below `entry_below`, and exit to flat `0` above `exit_above`, preserving position state between bars.

The rule definition is data, not uploaded executable code. Keep / Kill does not execute Python or Pine Script. The API has no code runner or arbitrary expression evaluator. Saving this draft must not be described as a measured verification result.

## JSON contract (schema version 1)

The browser and API accept `.json` strategy definitions up to 64 KB. Unknown fields are rejected. The API validates and stores the canonical JSON, then computes a `sha256:` hash over sorted, compact JSON. A generated `strategy_id` is returned with the saved draft.

Required identity fields are `name`, `symbol`, `timeframe`, `strategy_version`, and `rule`. Supported timeframes are `1m`, `5m`, `15m`, `1h`, `4h`, and `1d`. `period.start` and `period.end` are optional, but must be supplied together as timezone-aware ISO-8601 timestamps and the end must be later.

`market_data` is intentionally waiting-only: use `{ "source": "awaiting_upload", "upload_id": null }` (or omit the object and use the defaults). A user-uploaded market-data identifier is rejected until a candle-attachment contract exists. Historical CSV/Parquet imports remain a separate flow and are not attached to or inferred as this definition.

Costs default to UTC, 5 bps fee, 2 bps slippage, and `next_bar_open`. Timezone must be UTC or a valid IANA zone. Fees and slippage are finite values from 0 to 10,000 bps. Version 1 is long-only: `long_position` must be `1` and `flat_position` must be `0`.

Symbols are normalized to uppercase and may contain letters, numbers, dots, underscores, slashes, and hyphens. If a period is supplied, both timestamps must include a timezone, the end must be later, and neither may be more than two minutes in the future.

The remaining rule limits are:

- EMA: `fast_period` 2–1,000, `slow_period` 3–2,000, with fast below slow.
- RSI: `period` 2–1,000, `entry_below` and `exit_above` 0–100, with entry below exit.

Example, using only supported fields and no invented result:

```json
{
  "schema_version": "1",
  "name": "BTC EMA crossover",
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "strategy_version": "v1",
  "rule": {
    "family": "ema_crossover",
    "fast_period": 20,
    "slow_period": 50,
    "long_position": 1.0,
    "flat_position": 0.0
  },
  "period": { "start": null, "end": null },
  "market_data": { "source": "awaiting_upload" },
  "costs": {
    "timezone": "UTC",
    "fee_bps": 5.0,
    "slippage_bps": 2.0,
    "execution": "next_bar_open"
  },
  "description": "Long when the fast EMA is above the slow EMA; otherwise stay flat."
}
```

## Endpoints and inputs

- `POST /api/strategies/definitions` validates and saves an optional definition draft.
- `GET /api/templates/strategy-definition.json` downloads the canonical starter template.
- `GET /api/strategies/{strategy_id}/definition` downloads the saved canonical definition.
- The existing `POST /api/imports/preview` and `POST /api/strategies/import` are the primary verification path for CSV/Parquet timestamped strategy positions, with completed trades retained as diagnosis-only. Neither path infers a strategy definition from the file. Platform API ingestion is the intended next equivalent input; it is not a new browser contract in this pass.

Until the appropriate market data and research engine are connected, a saved definition or position import must not inherit demo metrics, generate synthetic positions, or appear as a running test.

## Demo and report boundaries

The local checkout now includes the recorded Argon reports. The default report set is real team-artifact output with `synthetic: false`: `experiments/investigation_argon_lane_a.json` (`btc-trend-24-72-demo`, `exp_dea9445d0576`) and `experiments/investigation_argon_meanrev.json` (`btc-meanrev-48-demo`, `exp_a79497cf70ec`). Each report carries `strategy_health`; the trend report is `within_training_range` for 43 of 45 validation blocks and its sealed arbiter is **INCONCLUSIVE**, while the mean-reversion report has 45 of 45 blocks inside the training range and names `agent::vol_median_05_1` as the accepted gate.

The one sealed mean-reversion look is recorded in `experiments/frozen_look_btc-meanrev-48-demo.json`. Gate versus always-on is **+27.3 percentage points** with a 90% interval of +15.3 to +36.2, and drawdown moves from 60.4% to 36.2%. The gated book's own net is −28.9% and its interval still contains zero, so this is not a profitability claim. The published **KILL** is for the always-on book because its drawdown passed the 40% cap and its net interval was entirely below zero; it is distinct from the gated-book comparison. `score_frozen` did not run the arbiter again.

The legacy `experiments/investigation_fixture.json` and `apps/api/fixtures/lane_b_investigation.json` remain synthetic fixtures and are excluded from these real-report claims. Do not invent an additional unlucky-versus-broken score, regime timeline, holdout result, or paper observation. When a requested evaluator result is unavailable, keep **not proven** / pending.
