# 07 · Evaluation protocol

"Testing on unseen data" is 25% of the score: *unseen data, real costs, a fitting benchmark and stated uncertainty.* This doc is the experiment we run and report, including if it comes out badly.

## Principle: planted truth on real prices

We cannot know whether a real trader's bot "really" died. So we build strategies where we **know**, run them on **real price history** (so noise, fat tails, vol clustering, event days are all real), and feed +EV only what a trader would have: the trade stream and a description.

Because the trade stream is generated *after* the strategy is fixed, this is a genuine forward stream and the sequential-test guarantees in [05 B4](05-judge-and-stats.md) hold here exactly.

## The strategy zoo (`plusev/sim/`)

Built on `vectorbt.Portfolio.from_signals` with fees 5 bp + slippage 5 bp (equities) / 10 bp + 10 bp (crypto). Each strategy is a signal generator plus an **edge injector** that controls the truth.

| Family | Signal | Truth variants |
|---|---|---|
| Mean reversion | z-score of 5-day return < −1.5 → long 3 days | alive / noise / dies at *T* |
| Trend following | 50/200 MA cross, ATR stop | alive / noise / dies at *T* |
| Breakout | 20-day high, 10-day exit | alive / noise / dies at *T* |
| Event fade | short vol-spike days, exit next close | alive / noise / dies at *T* |
| Regime-specific | mean reversion that *only* has edge in `realised_vol` = low | alive-in-regime (for the X-ray test) |

**Edge injection.** "Alive" = signals are mixed with a small amount of look-ahead on *future* returns (e.g. 10% weight on next-day return sign) so the strategy has a real, known, modest edge (target Sharpe ≈ 1.0 net). "Noise" = signals are a random permutation of the alive signals (same trade count and holding periods, zero edge). "Dies at *T*" = alive until trade index *T*, noise after. *T* is drawn uniformly from the middle 50% of the live window and **hidden** from the judge.

All of this is **labelled synthetic** per the track rules: the deck says exactly how the edge was planted.

Universe: 20 US large caps + SPY + 5 crypto pairs, 2015–2025 daily. Each (family, truth, symbol, seed) is one run. Target ≈ 600 runs; each is a vectorbt call, seconds.

## Splits

- **Backtest window:** 2015–2021 (training 2015–2019, sealed holdout 2020–2021).
- **Live window:** 2022–2025, streamed trade by trade to Kill or Keep.
- **Development set:** 1/3 of runs, used to build and tune. **Evaluation set:** 2/3, never looked at until the final run Sunday morning; the final-run commit hash goes in the deck.

## Experiments and metrics

### E1 · X-ray: does the envelope hold out-of-sample?

On `regime-specific` strategies (edge only in low vol): does the X-ray confirm the planted regime and *not* confirm others?
- **Power:** fraction of runs where the planted regime is confirmed on holdout.
- **False confirmation rate:** mean fraction of non-planted hypotheses confirmed. Target ≤ *q* = 0.10.
- On `noise` strategies: confirmations should be ≤ *q*.
- **Filter test:** net P&L, Sharpe, MDD of *filtered* vs *always* on the holdout, with bootstrap CI on the difference. Reported for alive and for regime-specific families.

### E2 · Kill or Keep: dead vs. unlucky

Stream live trades. Compare three decision rules:

| Rule | What traders actually do |
|---|---|
| **DD-20** | stop when drawdown > 20% |
| **3-loss** | stop after 3 consecutive losses, restart after 1 win |
| **+EV** | stop when the retirement e-detector alarms *or* the judge's recommendation is "stop" |

Metrics, per rule, across runs:
- **Detection delay** on `dies at T`: trades between *T* and stop. Median, 80% interval.
- **False kill rate** on `alive`: fraction of runs stopped within the live window.
- **P&L preserved:** net P&L of the rule vs. the oracle that stops exactly at *T* (for dying) or never (for alive), as a fraction. The single headline number.
- **ARL on alive strategies** for the e-detector (should be ≥ 300 trades by calibration).

### E3 · "N more trades" calibration

For every verdict that says "≈N more trades to a 90% answer", record the actual number of trades until the e-process stopped. Plot predicted vs. actual; report coverage of the 80% interval. If coverage is 60%, we say 60%.

### E4 · Decomposition accuracy

Inject known execution degradation (double slippage from a date) and known regime shifts (restrict the live window to high-vol only) into alive strategies. Check that the decomposition attributes the gap to the right component (sign and dominant share). Report confusion matrix.

### E5 · Sentiment: does the LLM add anything, and is it recall?

- IC of LLM sentiment vs. lexicon baseline on next-day returns, anonymised, 2015–2025.
- Memorisation guard result: IC(visible) − IC(anonymised) with CI.
- Does adding `sentiment` to the X-ray change any confirmed hypothesis? Count.

### E6 · Override Ledger (qualitative)

On replay of a `dies at T` and an `alive` run, simulate a nervous trader who overrides at every DD-20 trigger. Report the P&L cost of overrides vs. following +EV. This is the on-screen failure for the demo.

## Benchmarks (the "fitting benchmark" criterion)

- For the live decision: **DD-20 and 3-loss**, because they are what the forum uses.
- For the envelope: **run-always**, because the alternative to a filter is no filter.
- For the e-detector: **plain CUSUM on P&L** with a tuned threshold, because Algo Studio uses it.

We do not benchmark against buy-and-hold: +EV doesn't trade.

## Costs

All P&L is net of the fees and slippage above. The filter test is also reported at **2× costs** per the "survives higher costs" convention.

## Stated uncertainty

Every reported number carries a bootstrap or across-run interval. Where a number is a projection (N more trades) it is labelled as a projection with its assumption.

## Honest-result clause

If +EV does not beat DD-20 on P&L preserved, the deck says: "+EV did not beat the 20% drawdown rule on preserved P&L (x% vs y%, CI […]). It did reduce false kills from a% to b%. Here is why we think that is." The brief says this can still score top marks. We believe it.

## Reproducibility

`uv run eval/run_all.py --seed 7 --set eval` regenerates every table and figure in `eval/results/`. The deck cites the commit hash. Data pulls are cached in `data/` with their source and licence in [09](09-data-sources.md).
