# Keep or Kill: hidden-challenge pre-registration

Written 2026-11-08T12:25:41Z (UTC), before any `challenge` run of this adapter.
Only protocol-debugging PRACTICE runs (`generate` + `run` on a practice seed, outputs
kept outside the repo) may happen after this point and before the challenge runs. Rule
parameters below are frozen; they are not changed after any challenge output is seen.

## What is tested

The current Keep or Kill champion gate `agent::vol_median_05_1`
(experiments/investigation_argon_meanrev.json: allocation 1.0 when realized_vol_7d >
its research-period median, else 0.5) applied on top of the unchanged frozen demo
strategies, on the organisers' kit (`agentverse/finance`, `challenge`).

Adapter: `python3 -m packages.kit_adapter.kok --strategy {trend,mean_reversion} --mode {raw,gated}`
(code: packages/kit_adapter/rule.py, kok.py).

### Raw strategies (unchanged)

Loaded from the exact file A/kok_a/strategies.py (not re-implemented), on the kit's
price series as the close series, same bar counts as the demo:

- `trend` = `btc-trend-24-72-demo`: long when the 24-bar SMA > 72-bar SMA, else flat.
- `mean_reversion` = `btc-meanrev-48-demo`: enter when the 48-bar z-score < -1, exit when z >= 0.

Warm-up (NaN target, including zero-std windows) = flat. Windows are kept in BARS, not
re-scaled by time (they are the unchanged demo strategies). Both strategies are already
long/flat, so no long-only adaptation of the signal is needed; the kit allows no shorts.

### Gate (point-in-time, per path)

- Kit bars are daily (generator dates step by one calendar day; paths are 12-80 bars).
  KoK's realized_vol_7d = std of 168 hourly log returns = 7 days, so here
  `realized_vol[t]` = sample std (ddof=1) of the last 7 daily log returns (defined from bar 7).
- Threshold: EXPANDING median of realized_vol over bars strictly before t (this path only;
  there is no research period inside the kit).
- multiplier[t] = 0.5 if realized_vol[t] <= that median, else 1.0. Full size (1.0) when
  realized_vol[t] is undefined or no earlier value exists (warm-up). Never uses bars after t.
  (Note: KoK's own gate gives min allocation on missing features; this is moot here because
  realized_vol is defined from bar 7 and the strategies only trade from bar 47 / 71.)
- gated target = raw target x multiplier, in {0, 0.5, 1}.

### Execution constraint (important)

The kit's market runner only supports `buy` (spend ALL cash), `sell` (close ALL) or `hold`:
position is all-in long or flat. A 0.5 target cannot be executed. Pre-registered mapping:
**hold long only when target = 1.0; a 0.5 target is executed as flat (round down).**
So in-kit the gate acts as "trade only when 7-day vol is above its expanding median" - a
stronger de-risking than the champion's half size. The exact 0.5 rule is evaluated
separately with our own fractional simulator (packages/kit_adapter/sim.py), labelled as
NOT the kit.

## Runs

- Pack `markets`, 300 cases, self-serve `challenge` (fresh secret seed, cases in memory),
  `--max-seconds 1800`, `--project` = repo root. Order: mean_reversion first, then trend.
- Each challenge run once. A crash due to a bug may be fixed and rerun (logged below);
  no rerun because of the result.
- After each challenge: the seed revealed by the kit in the output folder is passed to
  `scripts/kok_challenge.py replay --seed <seed>`, the identical cases are regenerated with
  the kit's `generate`, and the RAW adapter is run with the kit's `run` on them.

## Reported comparison (fixed in advance)

Primary, per strategy, kit-executed, paired path by path (gated challenge vs raw replay):
- paths paired; gated better / raw better / identical (by final cash);
- two-sided exact sign test p on non-identical paths (same formula as the kit);
- mean and median of (gated - raw) final return (fraction of initial cash) and of
  (gated - raw) max drawdown (fraction); 90% bootstrap CI of the means;
- the kit's own market verdict vs buy-and-hold for the gated challenge run (as printed).

Secondary (context, not the claim):
- average exposure of gated relative to raw (offline kit-identical replay, cross-checked
  against the kit's final cash on every path);
- exposure-only baselines: in-kit, a half-size raw rounds to always-flat = cash, so gated
  vs cash is reported; with the fractional simulator, exact gated (x0.5/x1) vs raw and vs
  constant half-size raw (x0.5 always) on the same replayed cases.

Expectation stated in advance from the generator alone: mean_reversion can only trade on
paths of >= 49 bars (~46% of paths), trend on paths of >= 73 bars (~12%), so many paths
will be identical (both flat) and power will be low, especially for trend.

## Log

- 2026-11-08T12:25Z: pre-registration written. No challenge run yet.
