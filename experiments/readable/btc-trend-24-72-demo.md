# BTC trend 24/72

**Strategy verdict: Not proven** — applies to the original strategy, always on (Lane A arbiter)

**Finding.** Not proven. No filter passed, so the strategy stays unchanged.

**What it means.** The held-out intervals still contain zero, and the critic rejected every proposed filter. The agents proposed 3 filters; 3 were rejected. The critic rejected all of them; the reasons are listed with each filter.

**What to do next.** Don't add capital or change the strategy on this evidence. Re-test it on data after the held-out window. Any saved paper plan stays saved, not running.

## Research stages

| Stage | Window | What happened | Result |
|---|---|---|---|
| Training | 2018-02-08 to 2023-05-07 | The agents studied when the strategy makes and loses money, found 4 pattern(s), and tried 16 filter(s) on this data only. | Original strategy +276.0% after costs (90% interval -40.8% to +2069.1%); before costs +760.2%, worst drawdown 65.5%. |
| Validation | 2023-05-07 to 2025-02-02 | Code scored 6 rule(s) once on data the agents never saw: their proposals and the reference rules, after costs. | Original strategy +134.4% (90% interval +13.9% to +412.5%); cash +0.0%. |
| Held-out test | 2025-02-02 to 2026-10-31 | Scored once by Lane A's arbiter for the original strategy and its reference rules. No agent filter earned a look. | the held-out intervals still contain zero, and the critic rejected every proposed filter. |

## Filters that were checked

A filter only changes position size (none, half or full). Checked does not mean passed.

| Filter | Proposed by | Checked in | Outcome | Validation vs original | Own return on Validation | Why |
|---|---|---|---|---|---|---|
| Flat when Fear & Greed index is low (≤ 28) | Proposer agent | Training folds, Validation | **Rejected** | +32.0 pp | +166.5% | The critic rejected it: Severe sentiment regime shift between train and validation causes the gate to be almost always on in validation: allocation_mix is 1.0 for 96.58% of in-position decisions and 0.0… |
| Half size when Fear & Greed index is low (≤ 28) | Proposer agent | Training folds, Validation | **Rejected** | +15.8 pp | +150.2% | The critic rejected it: Because sentiment_regime shifted sharply between train and validation, this gate is almost always on at full size in validation: allocation_mix is 1.0 for 96.58% of in-position de… |
| Half size when 7-day price momentum is low (≤ -0.02482) | Proposer agent | Training folds, Validation | **Rejected** | -28.0 pp | +106.4% | The critic rejected it: The proposal is partly motivated by H1/H4 regime performance in trend_regime, where the bear bucket has only n_trades = 2 across 15278 decisions. |
| Simple reference rule | Reference rule (Lane A) | Training folds, Validation | **Comparison only** | -160.0 pp | -25.6% | A comparison the agents' filters must beat. Never a candidate. |
| LightGBM model filter | Reference rule (Lane A) | Validation | **Comparison only** | -171.2 pp | -36.8% | A comparison the agents' filters must beat. Never a candidate. |
| Lane A regime filter | Reference rule (Lane A) | Training folds, Validation | **Comparison only** | -20.3 pp | +114.1% | A comparison the agents' filters must beat. Never a candidate. |

Also tried on Training only and not taken further (16): Flat when 7-day volatility is high (> 0.00753); Flat when trading volume vs normal is low (≤ -0.07709); Flat when Fear & Greed index is low (≤ 39); Flat when 7-day price momentum is low (≤ 0.004282); Half size when trading volume vs normal is low (≤ -0.2419); Half size when 7-day volatility is high (> 0.00753); Half size when Fear & Greed index is low (≤ 39); Flat when distance below the recent high is low (≤ -0.04068); Flat when 7-day price momentum is low (≤ -0.02482); Half size when Fear & Greed index is low (≤ 28); Flat when Fear & Greed index is low (≤ 28); Half size when 7-day price momentum is low (≤ -0.02482); p13 rvol q80 half; p14 fg q33 rvol q80 half; p15 mom7d volz q20 half; p16 volz q20 half.

## How the agents got there

1. **Diagnostic agent** (AI agent) — Found 4 pattern(s) in when the strategy works. On TRAIN, btc-trend-24-72-demo generates a gross_return of 7.602 across turnover of 752, but fees (4.402) and slippage (0.4402) reduce net_return to 2.760 (90% CI [-0.4083, 20.69]).
   - Works better in an up-trend (medium confidence)
   - Works better in deep liquidity, thin liquidity (medium confidence)
   - Works better in greedy sentiment, low volatility (medium confidence)
   - Works worse in a sideways market (low confidence)
2. **Context agent** (AI agent) — Checked market mood around the best and worst weeks. Across the 4 best and 4 worst train weeks, overall Fear & Greed levels and 7-day changes do not cleanly separate good and bad weeks, though sample size is small (4 weeks per side).
   - 2 of the 4 best train weeks (best_week_1 and best_week_4) co-occurred with a greed-to-fear flip in the prior 3 days (72 bars), compared with the train base rate of 0.0956072351421189 (binomial_p_valu… (moderate)
   - 0 of the 4 worst train weeks (worst_week_1, worst_week_2, worst_week_3, worst_week_4) co-occurred with either a fear-to-greed flip (train base rate 0.0930013576840538, binomial_p_value = 1) or a gree… (none)
   - Starting Fear & Greed levels and in-week averages do not cleanly separate best and worst weeks compared with the train mean Fear & Greed of 42.7779111120808. (weak)
   - Prior 7-day Fear & Greed changes and extreme sentiment shares overlap across best and worst weeks rather than separating them. (weak)
3. **Proposer agent** (AI agent) — Tried 16 filter(s) on Training, proposed 3. Each filter only changes position size. The strategy's own signals are never touched.
   - Flat when Fear & Greed index is low (≤ 28): H3 shows positive mean_net_return in sentiment_regime=greed (6.813e-05) while fear spans zero ([-4.077e-05, 6.468e-05]).
   - Half size when Fear & Greed index is low (≤ 28): Based on H3 (weak returns in sentiment_regime=fear), scaling allocation to 0.5 when fear_greed <= 28 preserves avg_holding_bars (63.47) while reducing turnover…
   - Half size when 7-day price momentum is low (≤ -0.02482): H1 and H4 show strong returns in trend_regime=bull (mean_net_return 0.0001275) and weak/negative returns in non-bull regimes.
4. **Code: scoring** (Code) — Scored 6 rule(s) on Validation and Training folds. 2 of 3 agent filter(s) beat the original on Validation. Reference rules were scored the same way.
   - Flat when Fear & Greed index is low (≤ 28): +32.0 pp vs the original, own return +166.5%
   - Half size when Fear & Greed index is low (≤ 28): +15.8 pp vs the original, own return +150.2%
   - Half size when 7-day price momentum is low (≤ -0.02482): -28.0 pp vs the original, own return +106.4%
   - Simple reference rule: -160.0 pp vs the original, own return -25.6%
5. **Code: health check** (Code) — Asked: unlucky or broken?. 43 of 45 validation 14-day blocks fall inside the training range [-0.1334, +0.1952]: a loss alone does not show the strategy broke.
6. **Critic agent** (AI agent) — Challenged 3 filter(s): rejected 3. The critic looks for leakage, overfitting and fragile samples. It can block a filter, not approve one.
   - Flat when Fear & Greed index is low (≤ 28): rejected — Severe sentiment regime shift between train and validation causes the gate to be almost always on in validation: allocation_mix is 1.0 for 96.58% of in-position decisions and 0.0 for only 3.42%.
   - Half size when Fear & Greed index is low (≤ 28): rejected — Because sentiment_regime shifted sharply between train and validation, this gate is almost always on at full size in validation: allocation_mix is 1.0 for 96.58% of in-position decisions and 0.5 for…
   - Half size when 7-day price momentum is low (≤ -0.02482): rejected — The proposal is partly motivated by H1/H4 regime performance in trend_regime, where the bear bucket has only n_trades = 2 across 15278 decisions.
   - *Changed the conclusion:* The filter with the best Validation number (Flat when Fear & Greed index is low (≤ 28), +32.0 pp) was rejected by the critic, so it could not be selected.
7. **Code: selection rule** (Code) — No filter earned the held-out test. The rule was fixed before the run: beat the original with an interval above zero, beat cash, change something real, and not be rejected by the critic.
   - Selected: none
   - no agent gate met the pre-registered rule
8. **Lane A arbiter** (Code) — Strategy verdict: INCONCLUSIVE. the held-out intervals still contain zero, and the critic rejected every proposed filter.
   - Applies to: the original strategy, always on

## Take away

**Strategy.** The analysis used this strategy's positions. Its definition and the file that generates them are listed here; this report itself contains no runnable code.
- Rule: Long BTCUSDT when the 24-hour moving average of the close is above the 72-hour average; otherwise flat.
- Parameters: `{"fast_bars": 24, "slow_bars": 72, "bar": "1h", "side": "long or flat"}`
- Source: `A/kok_a/strategies.py (_trend, version trend-sma-24-72-v1)`

**Selected filter.** No filter was selected, so there are no filter settings to take away.

**Evidence.**
- Full agent report (every claim linked to a tool result): `experiments/investigation_argon_lane_a.json`
- Unlucky or broken check: `ev_strategy_hea_36802850f0`

Nothing here places orders. Any saved paper plan stays saved, not running.

---
*code (packages/research_agents/presentation.py); no new numbers, no new decisions.*
