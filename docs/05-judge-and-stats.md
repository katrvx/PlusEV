# 05 · Judge and statistics

The judge is deterministic, versioned, and contains no LLM calls. This doc is the maths. Each method states what it guarantees, what it assumes, and what it does *not* guarantee, because that honesty is 25% of the score ("stated uncertainty") and the first thing a Jane Street judge probes.

Notation: a trade has net P&L *x* (after fees and slippage, in R-multiples or % of equity). Backtest trades *B*, live trades *L*. Regime tag *g* per trade.

---

## Part A · X-ray (operating envelope)

### A1. Conditional performance

For each registered hypothesis *h = (feature, bucket, direction)*, split *B* into trades **in** the bucket (*B_in*) and **out** (*B_out*). Statistic: difference in mean net P&L per trade, standardised:

```
d_h = (mean(B_in) − mean(B_out)) / pooled_sd
```

p-value by **stationary bootstrap** of the trade sequence (`arch.bootstrap.StationaryBootstrap`, expected block length chosen by Politis–White), because trades are serially dependent (overlapping holding periods, vol clustering). An iid bootstrap would understate variance and over-admit. 2,000 resamples.

### A2. Multiple-testing correction

We tried *m* hypotheses (the ledger's count, including refused duplicates? **No**: refused duplicates don't consume a test, but they are reported, and the slot budget caps *m*). Correct with **Benjamini–Hochberg** at FDR *q* = 0.10 over the *m* p-values (`statsmodels.stats.multitest.multipletests`). Guarantee: expected fraction of false "green/red" labels among those we report ≤ 10%, under positive dependence (BH-PRDS), which holds approximately for bucket tests on the same trade set; we also report Benjamini–Yekutieli (valid under arbitrary dependence) as the conservative number.

**Why this and not deflated Sharpe:** deflated Sharpe corrects one strategy's Sharpe for the number of strategy variants tried. Here the object is many regime slices of one strategy; BH on slice tests is the direct tool. We cite both so the judges see we know the difference.

### A3. Sealed holdout confirmation

The backtest window is split by time: **training** (first 70%) and **holdout** (last 30%). Terciles, HMM fit, and all A1/A2 steps use training only. The holdout file is encrypted at rest; opening it writes a receipt `{strategy_id, hypotheses_hash, ts}` to the audit log, and the judge refuses a second opening for the same `strategy_id`.

On the holdout: for each BH survivor, recompute *d_h* and its bootstrap CI. A hypothesis is **confirmed** if the holdout effect has the same sign and the one-sided 90% CI excludes zero. Report three numbers, always: **proposed → survived training → confirmed on holdout.**

**What the holdout does not protect against:** structure shared by both windows (a regime that was green in both because of one 2020-style episode). We report the number of distinct regime *episodes* behind each confirmed hypothesis; fewer than 3 episodes → flagged "thin".

### A4. The envelope and the filter test

The envelope is the set of confirmed hypotheses with their effect sizes. The actionable question: **does trading only in green regimes beat trading always?** On the holdout, after costs, compare:

- *Always*: all holdout trades.
- *Filtered*: holdout trades not in any confirmed-red bucket.

Report net P&L, Sharpe, max drawdown, trade count, and a bootstrap CI on the difference. **If filtered does not beat always, we say so.** The track brief: an honest miss can score top marks.

---

## Part B · Kill or Keep (live diagnosis)

### B1. Is this drawdown normal?

From *B*, build the **drawdown distribution** by stationary bootstrap of the trade sequence: resample 5,000 equity paths of the same length as the live window, record max drawdown of each. The live drawdown's percentile in that distribution is the headline number: *"your 15% drawdown is at the 78th percentile of what your own backtest implies for a 40-trade window"* (equivalently ≈1.2σ if roughly normal; we report the percentile, not σ, in the UI).

Rule of thumb for the explainer: < 90th percentile → "within expectation"; 90–99 → "unusual, keep watching"; > 99 → "outside what the backtest implies".

### B2. Expectancy drift, regime-conditioned

Naive drift: `mean(L) − mean(B)`. Regime-conditioned drift: for each regime bucket present in *L*, compare `mean(L_g)` to `mean(B_g)` and aggregate by *L*'s regime mix:

```
drift_cond = Σ_g w_g · (mean(L_g) − mean(B_g)),   w_g = |L_g| / |L|
```

If naive drift is large but conditional drift is small, the live window is simply in regimes where the backtest also did badly. That is the "weather, not disease" verdict, and it's a number, not a vibe.

### B3. Decomposition: execution / signal / regime

Define for each trade the **gross** P&L (at signal prices) and **net** (actual fills, fees). Then:

```
gap_total      = mean_net(L) − mean_net(B)
gap_execution  = [mean_net(L) − mean_gross(L)] − [mean_net(B) − mean_gross(B)]
gap_regime     = Σ_g (w_g^L − w_g^B) · mean_gross(B_g)          # mix effect at backtest returns
gap_signal     = gap_total − gap_execution − gap_regime           # what's left: the edge itself
```

Each component gets a bootstrap CI. This is an Oaxaca-style decomposition; the "signal" term is the residual, which we say explicitly. If `gap_execution` dominates → fills got worse (broker, size, time of day). If `gap_regime` dominates → weather. If `gap_signal` dominates → the edge itself has moved; that is the decay case.

Requires gross P&L in the trade record. If the trader's CSV lacks signal prices, execution and signal are reported jointly and the UI says so.

### B4. How many more trades until we know

The question the forum can't answer. We frame it as a sequential test of **H0: live expectancy ≤ 0** (or ≤ a break-even threshold δ) against **H1: live expectancy = backtest expectancy μ_B**.

**Method: betting e-process** (`ville.BettingTest`, fallback in `judge/sequential.py`). Wealth *W_0 = 1*; on each live trade with bounded standardised outcome *y_t ∈ [−1, 1]*:

```
W_t = W_{t−1} · (1 + λ_t · y_t),    λ_t ∈ [0, 1) chosen from trades < t (e.g. GRAPA / aGRAPA)
```

Under H0, *W* is a nonnegative supermartingale, so by **Ville's inequality** P(sup_t W_t ≥ 1/α) ≤ α. We stop and declare "edge alive" when *W_t ≥ 1/α* with α = 0.10. Symmetrically a second e-process bets on decay.

**"N more trades":** we simulate the e-process forward from the current wealth, drawing future trades from the backtest's regime-matched distribution (bootstrap), and report the median and 80% interval of trades-to-stop. It is a **projection under the assumption that the future looks like the regime-matched backtest**; we label it exactly that way in the UI.

**Guarantee:** anytime-valid: the trader can look after every trade and the error rate still holds. **Not guaranteed:** the projection's accuracy; it's conditional on the backtest being representative.

### B5. Retirement detector (edge decay)

Separate from B4: a **restarted e-detector** (CUSUM-like) that bets daily that live expectancy < δ, reset whenever wealth drops below 1. An alarm fires when wealth ≥ 1/α_det. For a change detector the right guarantee is **average run length to false alarm**, not an α-level; we calibrate α_det on the planted-truth suite ([07](07-evaluation-protocol.md)) to an ARL of ≥ 300 trades on alive strategies, and report detection delay on dying ones. `ruptures` (PELT) runs offline to estimate *when* the change happened, for the explanation.

### B6. "Probability the edge is alive"

The UI's single number. **Not** an e-value and **not** a p-value. It is a Bayesian posterior under an explicit model: prior from the backtest (μ_B, σ_B shrunk toward 0 by a factor that encodes "backtests flatter"), likelihood from live trades, regime-conditioned. We print the prior assumptions next to the number. Judges can disagree with the prior; they can't accuse us of hiding it.

---

## Part C · What we assume, in one list

- Trades within a regime bucket are exchangeable enough for a block bootstrap. (Violated by strong trends in P&L; mitigated by stationary bootstrap.)
- Regime labels at trade entry are the relevant conditioning. (A 3-day trade spans regimes; we tag at entry and note it.)
- BH-PRDS for the correction; BY reported as conservative alternative.
- The e-process guarantee needs bets fixed before outcomes and a proper conditional null. True for live/paper streams and for our planted-truth simulator (data generated after the strategy is fixed). On historical replay of a *real* strategy, the trader may already know the period; we label replay results as replay.
- Daily regime tags cannot see sub-daily structure. Out of scope.

## Part D · Properties we test (pytest + hypothesis)

- On pure-noise trades, the X-ray confirms ≤ *q* of hypotheses on average (across seeds).
- On a strategy with a planted regime effect of size *d*, the X-ray confirms it with power ≥ 0.8 at the planted sample size.
- The e-process on noise exceeds 1/α with frequency ≤ α over 10,000 runs.
- `features_as_of(ts)` is invariant to data after *ts*.
- Opening the holdout twice raises.
