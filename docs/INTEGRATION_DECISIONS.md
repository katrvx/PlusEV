# Integration decisions

Recorded while putting current `main` (Lane B), `lane-c` (the API and web app), and Lane A on one branch. The spec in `KEEP_OR_KILL_PROJECT_SPEC.md` still wins if this note disagrees with it.

Lane A now also carries the spec items that were still open on this lane: 7-day momentum, 14-bar ATR, and trailing price drawdown; a 2-bar embargo on the LightGBM fit; expanding walk-forward folds inside train; a training-distribution range for a 14-day path on the unstarted paper plan; and validation fee checks at half and double cost. News stays omitted because the snapshot has no first-seen archive. Funding stays zero because the venue is spot. The screen shows the arbiter's words: KEEP, MODIFY, RESTRICT, MONITOR, KILL, INCONCLUSIVE. MODIFY is a regime overlay that beat always-on. RESTRICT is a smaller overlay that stays inside the drawdown cap. COMBINE is not emitted for a single book.

## Which Lane B

The agents, tools, and contracts are the ones on current `main`. The earlier local copies of `investigate.py` and `tools.py` were not kept.

One change sits on top of that code. If the loader's runner has `rule_spec`, that spec is the simple-rule competitor. Lane A puts the rule it actually simulated there: full size only when lagged 24h momentum is positive and 7d volatility is at or below the train median, otherwise allocation 0. The synthetic stand-in has no `rule_spec`, so it still builds `rule_gate_spec(train_quantiles)`, whose false allocation is 0.5. Lane B's own tests keep using that stand-in.

The arbiter scores this competitor through `arbiter_evaluate`. That path does not require the momentum threshold of 0 to sit on the agent quantile grid. Agents still may only test allowlisted threshold gates on train.

## What Lane A returns to Lane B

`GateEvaluation` follows the contract in `packages/contracts_lane_b`:

- `delta_net_return_vs_always_on` is the difference of compounded returns, not the sum of bar differences.
- `ci_delta` is a 90% moving-block bootstrap of that same difference. Both series share each draw. Block length is 24 hours.
- `ci_net_return` is a 90% moving-block bootstrap of the compounded return.
- `allocation_mix` is the share of in-position bars at 0, 0.5, and 1. Flat targets are not in the mix. `n_decisions` is every bar in the split and `n_in_position` is the denominator.
- Cost rows use the same compounded return as the always-on baseline. `switching` is only the extra turnover a gate adds, so on the unchanged strategy it is 0, and gross − fees − slippage − switching equals net.
- Bootstrap draws are seeded from the policy body, not its name. The ready path uses 2000 resamples.
- The LightGBM gate fits on early train and calibrates on the last 25% of train. Validation is left out of that fit. `spec()` carries the seed and a hash of the fitted model.

`load_for_lane_b` returns the development view. Test-window dates stay, so a news request that crosses the holdout can still be refused. Test metrics, the verdict, and the paper plan are removed. `GateRunner.evaluate` refuses `split="test"`. `score_frozen` is the one sealed look, and a changed body under an id that was already scored is refused.

## What the API will score

`apps/api/engine.py` is the only path from an upload to Lane A and Lane B. `research_engine` is true because this path exists.

| Import | Result |
|---|---|
| Seeded demo strategy | The checked-in illustrative fixture. `mode` stays `demo`. |
| BTCUSDT positions, timeframe `1h` / `1hr` / `1hour` / `60m` / `60min` / `hourly` | Lane A, then Lane B. `mode` is `measured` when the run finishes. |
| Trade log | `awaiting_engine`, empty metrics. A trade log has no target position at each decision, so a gate cannot be simulated. |
| Any other symbol or timeframe | `awaiting_engine`, empty metrics. This snapshot is Binance spot BTCUSDT 1h from 2024-11-01 through 2026-10-31. |
| Positions that leave fewer than 30 consecutive usable hours | `failed`, empty metrics, `mode` `pending`. The January 2024 example CSVs do this on purpose: they do not overlap the snapshot. |

Demo numbers are never copied onto an upload.

Imported targets are matched to the snapshot's decision times. Hours with no imported position are dropped. Only the longest contiguous run of hourly decisions is scored. A gap is not treated as a continuous position path.

If the strategy is in the market too rarely to fit LightGBM (fewer than 40 in-market train rows or 10 validation rows), the run fails. A gate is not invented to fill that hole.

## Costs

An upload's stored `fee_bps` and `slippage_bps` are passed into the simulator. The import form's defaults are 5 bps and 2 bps. Lane A's own experiments still use 10 bps plus 1 bp when no override is passed. Either way the cost is an assumption, and the result says which assumption was used.

## Verdicts on the screen

Lane A's arbiter remains the verdict. Lane B's `candidate_for_frozen_test` / `INCONCLUSIVE` says whether an agent gate earned one sealed look. It does not replace the arbiter.

The screen stores the arbiter's verdict: `KEEP`, `MODIFY`, `COMBINE`, `RESTRICT`, `MONITOR`, `KILL`, `INCONCLUSIVE`. Older records that still say `ACTIVATE CONDITIONALLY` or `REDUCE` are shown as Modify and Restrict. The recommendation text keeps the arbiter's reasons.

`holdout_frozen` is true on a completed measured run: the pre-registered policies were fixed before the test look. `test_evaluated` is true only when that verdict is not `INCONCLUSIVE`, so an abstention cannot be frozen into a 14-day paper test. Lane A's own paper plan stays `completed=false` and `approved=false`.

## Chart and table

The suggested line is the policy the arbiter selected. It is not an agent gate that was never shown the sealed test. If an agent champion was accepted, it is scored once and added to the comparison table. If the investigation itself fails, Lane A's pre-registered comparison is still returned, and the failure is listed as a limitation.

The equity index is the compounded path times 100, so the chart's "100 is the starting balance" line matches the first bar's growth. Series longer than about 1,500 points are thinned for the chart. The metrics use the full series.

Two presentation compromises, both because the current UI formats the number directly:

- A missing Sharpe (zero variance) is sent as 0.
- Max drawdown is sent as a negative number, so the signed percent formatter shows a drop. Lane A stores drawdown as a positive fraction.

Regime cards are the compounded train return of the unchanged strategy in each trend bucket and each volatility bucket. `confidence_low` and `confidence_high` are that same number. A separate interval for the compounded bucket return is not computed.

## Agents on an upload

The worker runs Lane B in deterministic fallback unless `KOK_AGENT_MODEL` is set. The default bootstrap is 200 resamples and the LightGBM gate uses 120 trees. The API tests pass smaller values and do not change those defaults.

The investigation JSON is `experiments/investigation_<experiment_id>.json`. `GET /api/investigations` reads it. Generated `investigation_exp_*.json` files are gitignored. The checked-in stand-in is not.

## Left unwired

`plusev/`, the Streamlit app, and the kit scripts do not call this path. News is still omitted. There is no walk-forward, purge, or embargo beyond the single 60/20/20 chronological split.
