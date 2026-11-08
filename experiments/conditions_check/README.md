# Market conditions behind the gates, and timing vs taking less risk

Training and Validation only. Nothing in this folder read the held-out test, and nothing here is a new verdict.
The published results (mean reversion: Kill; trend: Not proven) are unchanged.

## What the gates can condition on

| Condition | Status | Feature(s) | Notes |
|---|---|---|---|
| Trend, short vs longer window | **Supported** | `momentum_24h`, `momentum_7d` | Both allowlisted, point in time. Lane A also labels up / down / sideways for each window (`trend_regime`, `trend_7d_regime`), which the diagnostic agent sees in `regime_performance`. |
| Volatility level | **Supported** | `realized_vol_7d`, `atr_14` | |
| Volatility change vs baseline | **Supported (added today)** | `vol_ratio_24h_7d` | Last-24h volatility / 7-day volatility (Lane A, point in time, coverage 100%). Now on the Lane B allowlist. Above 1 = volatility rising. |
| Drawdown from recent high | Supported | `price_drawdown` | |
| Spreads, order-book depth, quoted slippage | **Missing data** | none | No historical spread or depth data exists in our snapshot. Costs stay fixed at 10 bp fee + 1 bp slippage for every policy. |
| Volume change | Supported, **labelled as a proxy** | `volume_zscore` | Traded volume vs its own 7-day baseline. It is not liquidity in the market-microstructure sense, and reports call it "volume". |
| Market sentiment | Supported where timestamps are reliable | `fear_greed` | Daily index, used from the next day, 100% coverage on Training. |
| News | **Refused** | `news_sentiment` | 0% coverage: no archive with first-seen timestamps. |

**Bounds (unchanged).** The only family is `threshold_gate`, with 1 or 2 conditions. Thresholds come from the Training quantiles 0.2, 0.33, 0.5, 0.67 and 0.8, and allocations are 0, 0.5 or 1. At most 12 agent Training tests run per investigation, and every attempt is logged.

**Direction comes from the strategy.** The agents take each condition's direction from this strategy's own Training evidence. In the rerun below:
- Low volatility is a weakness for mean reversion and a strength for trend.
- Rising volatility (`vol_change_regime=above_baseline`) is a weakness for mean reversion and a strength for trend.

## Timing vs taking less risk

**What changed in code.** For every proposal, the arbiter now also scores, on Validation and with identical costs:
- constant half size;
- a constant frozen at the gate's average Training size. This is the same average exposure with no timing, the same method as Lane A's `exposure_matched_spec`.

These comparisons are reported per filter. They are **diagnostic and not part of the selection rule**, which was fixed before the run. Making them an acceptance criterion needs fresh data after 2026-10-31.

**A third check, in `scripts/timing_check.py`.** It adds a constant at the gate's *actual* Validation size. This matters when a condition becomes more or less common on Validation than on Training; it is set on Validation, so it is a diagnostic only.

**One held-out look per test window.** `frozen.check_window` refuses any second look at an experiment's held-out window, whatever the policy. It is enforced in `scripts/frozen_look.py` and in the ledger. Once a window is open, its result can only be used diagnostically.

## Results, Validation (2023-05-07 to 2025-02-02)

All net returns are compounded, after costs. Source: `timing_<strategy>.json` (run by `python3 scripts/timing_check.py --report <committed report>`).

### Mean reversion (`btc-meanrev-48-demo`): the filter selected in the committed Argon run

**Exact rule** (`agent::vol_median_05_1`, frozen in `experiments/investigation_argon_meanrev.json`, commit ad3dff1):

```json
{"family": "threshold_gate",
 "conditions": [{"feature": "realized_vol_7d", "op": ">", "threshold": 0.00640924015585452}],
 "allocation_when_true": 1.0, "allocation_when_false": 0.5, "thresholds_selected_on": "train"}
```

In words: full size when 7-day volatility is above its Training median, otherwise half size.

| Policy (Validation, same costs) | Net return | Exposure | Max drawdown |
|---|---|---|---|
| Gate | **+7.3%** | 0.20 | 18.9% |
| Original strategy (always on) | −19.5% | 0.35 | 31.2% |
| Cash | 0.0% | 0 | 0 |
| Constant half size | −8.4% | 0.18 | 16.2% |
| Constant 0.744x (the gate's Training size) | −13.5% | 0.26 | 23.6% |
| Constant 0.567x (the gate's Validation size, diagnostic) | −9.7% | 0.20 | 18.3% |
| Simple rule | −40.7% | 0.03 | 41.2% |
| Lane A regime filter (current) | +38.8% | 0.03 | 12.0% |

**Reading.**
- On Validation the gate beats half size by 15.7 pp, the Training-size constant by 20.8 pp and the Validation-size constant by 17.0 pp. That is some evidence of timing on Validation, not proof, because Validation was also used to select.
- Lane A's regime filter did better on Validation (+38.8%).
- On the one held-out look the gate still lost **−28.9%**, against −56.2% for the original (+27.3 pp, drawdown 60.4% → 36.2%).
- We did not compute the same-size constants on the held-out window: that would be a second look. The Kill for the original strategy stands, and the filter is not approved.

### Trend (`btc-trend-24-72-demo`): no filter selected

| Proposal | Net (Validation) | vs half size | vs constant at its Training size | vs constant at its Validation size | Outcome |
|---|---|---|---|---|---|
| Flat when Fear & Greed ≤ 28 | +166.5% | +109.4 pp | +81.6 pp (0.70x) | +38.0 pp (0.97x) | Rejected by the critic |
| Half size when Fear & Greed ≤ 28 | +150.2% | +93.1 pp | +41.5 pp (0.85x) | +18.7 pp (0.98x) | Rejected by the critic |
| Half size when 7-day momentum ≤ −0.0248 | +106.4% | +49.4 pp | −13.4 pp (0.92x) | −17.4 pp (0.94x) | Rejected |

Benchmarks on the same window: original +134.4%, half size +57.0%, cash 0%, simple rule −25.6%, Lane A regime filter +114.1%.

The Fear & Greed gates sat at about 0.97x size on Validation, against about 0.70x on Training, because fear became rare. Their edge rests on the 3% of bars where they cut size, which is why the critic rejected them. That rejection stands.

### Rerun with today's code (deterministic agents, not Gemini)

Files: `btc-meanrev-48-demo_fallback.json`, `btc-trend-24-72-demo_fallback.json`. These runs used the new feature and benchmarks.

**Mean reversion.** Selected "flat when 7-day volatility ≤ 0.006409", the same condition Argon's critic rejected.
- Validation: +38.8%, versus +47.1 pp over half size and +46.9 pp over a constant at its 0.49x Training size.
- It is off 87% of the time on Validation.
- **It cannot take a held-out look**: this strategy's window is already open. It needs fresh data.

**Trend.** No filter selected.

To run the same check with the LLM agents: `KOK_AGENT_MODEL=google:gemini-4-argon GEMINI_API_KEY=... python3 scripts/run_investigation.py --lane-a --experiment-id <strategy> --out experiments/conditions_check/<strategy>_argon.json`.
