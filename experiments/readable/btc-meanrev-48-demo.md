# BTC mean reversion 48

**Strategy verdict: Kill** — applies to the original strategy, always on (Lane A arbiter)

**Finding.** Kill the original strategy. The agents' best filter lost less, but still lost money.

**What it means.** On the held-out test the filter beat the original by +27.3 pp (90% interval +15.3 to +36.2 pp), and its own return was -28.9%. Most of that gain comes from holding a smaller position. A filter that loses less is not a new Keep verdict.

**What to do next.** Stop running this strategy. Do not deploy the filter as a fix. Any saved paper plan stays saved, not running.

## Research stages

| Stage | Window | What happened | Result |
|---|---|---|---|
| Training | 2018-02-08 to 2023-05-07 | The agents studied when the strategy makes and loses money, found 3 pattern(s), and tried 6 filter(s) on this data only. | Original strategy -89.6% after costs (90% interval -98.3% to -40.9%); before costs -56.2%, worst drawdown 92.4%. |
| Validation | 2023-05-07 to 2025-02-02 | Code scored 6 rule(s) once on data the agents never saw: their proposals and the reference rules, after costs. | Original strategy -19.5% (90% interval -55.9% to +51.1%); cash +0.0%. |
| Held-out test | 2025-02-02 to 2026-10-31 | Opened once (2026-11-08), after the report that chose the filter was committed. Nothing was chosen here. | Beat the original by +27.3 pp (90% interval +15.3 to +36.2 pp). Worst drawdown 60.4% → 36.2%. Its own return was -28.9% — it still lost money. |

## Filters that were checked

A filter only changes position size (none, half or full). Checked does not mean passed.

| Filter | Proposed by | Checked in | Outcome | Validation vs original | Own return on Validation | Why |
|---|---|---|---|---|---|---|
| Half size when 7-day volatility is low (≤ 0.006409) | Proposer agent | Training, Training folds, Validation, Held-out test | **Selected for further testing · not approved** | +26.8 pp | +7.3% | Earned one held-out test, then lost money there (-28.9%), so it is not approved. Losing less than the original is not a fix. |
| Flat when 7-day volatility is low (≤ 0.006409) | Proposer agent | Training, Training folds, Validation | **Rejected** | +58.2 pp | +38.8% | The critic rejected it: Due to a severe volatility regime shift between train and validation, this fixed train-median threshold leaves the gate off (0.0 allocation) 86.68% of the time and active only 13.… |
| Flat when 7-day volatility is low (≤ 0.00753) | Proposer agent | Training, Training folds, Validation | **Rejected** | +47.1 pp | +27.6% | The critic rejected it: On validation, the gate is almost always off: allocation_mix is 93.89% at 0.0 and only 6.109% at 1.0, resulting in an exposure of just 0.02147 and only 44 position switches across… |
| Simple reference rule | Reference rule (Lane A) | Training folds, Validation | **Comparison only** | -21.2 pp | -40.7% | A comparison the agents' filters must beat. Never a candidate. |
| LightGBM model filter | Reference rule (Lane A) | Validation | **Comparison only** | -41.3 pp | -60.8% | A comparison the agents' filters must beat. Never a candidate. |
| Lane A regime filter | Reference rule (Lane A) | Training folds, Validation | **Comparison only** | +50.6 pp | +31.1% | A comparison the agents' filters must beat. Never a candidate. |

Also tried on Training only and not taken further (3): Flat when 14-bar average true range is low (≤ 0.008876); Flat when 7-day volatility is low (≤ 0.006409) or 7-day price momentum is low (≤ -0.02482); Flat when 7-day volatility is low (≤ 0.00535).

## Timing or just less risk? (Validation, same costs)

| Filter | vs constant half size | vs constant at its Training size | vs constant at its Validation size | Read |
|---|---|---|---|---|
| Half size when 7-day volatility is low (≤ 0.006409) | +15.7 pp | +20.8 pp (constant 0.74x) | +17.0 pp (constant 0.57x) | Beat constant half size and a constant of the same average size on Validation: some evidence of timing, not proof (Validation was also used to select). Its average size changed between Training and Validation, so treat the comparison with care. |
| Flat when 7-day volatility is low (≤ 0.006409) | +47.1 pp | +46.9 pp (constant 0.49x) | +40.7 pp (constant 0.13x) | Beat constant half size and a constant of the same average size on Validation: some evidence of timing, not proof (Validation was also used to select). Its average size changed between Training and Validation, so treat the comparison with care. |
| Flat when 7-day volatility is low (≤ 0.00753) | +36.0 pp | +33.0 pp (constant 0.34x) | +28.4 pp (constant 0.06x) | Beat constant half size and a constant of the same average size on Validation: some evidence of timing, not proof (Validation was also used to select). Its average size changed between Training and Validation, so treat the comparison with care. |

Source: `experiments/conditions_check/timing_btc-meanrev-48-demo.json`. Diagnostic only: the selection rule fixed before the run is unchanged.

## The one held-out look

Beat the original by +27.3 pp (90% interval +15.3 to +36.2 pp). Worst drawdown 60.4% → 36.2%. Its own return was -28.9% — it still lost money.
Source: `experiments/frozen_look_btc-meanrev-48-demo.json`.

## How the agents got there

1. **Diagnostic agent** (AI agent) — Found 3 pattern(s) in when the strategy works. On the train split, the strategy loses money overall (always_on gross_return -0.5621, net_return -0.8963, 90% CI [-0.9831, -0.4089], Sharpe -0.5991).
   - Works worse in low volatility (high confidence)
   - Works better in high volatility (low confidence)
   - Works worse in a down-trend (low confidence)
2. **Context agent** (AI agent) — Checked market mood around the best and worst weeks. Across the 4 worst and 4 best train weeks, pre-week Fear & Greed levels, 7-day changes, and 3-day sentiment flips do not separate good and bad weeks.
   - Starting Fear & Greed levels do not clearly separate the 4 worst weeks (52, 41, 61, 13) from the 4 best weeks (61, 14, 94, 75) compared with the train base rate mean_fear_greed of 42.7779111120808; b… (none)
   - 7-day Fear & Greed changes prior to week start were mixed across both groups: +10, +2, -7, and +3 before worst_week_1, worst_week_2, worst_week_3, and worst_week_4 respectively, versus -6, -27, +1, a… (weak)
   - Greed/fear flips in the 3 days before a week started did not separate best and worst weeks: a fear-to-greed flip occurred in 1 of 4 worst weeks (worst_week_1) and 1 of 4 best weeks (best_week_1) comp… (none)
   - During the weeks themselves, all 4 worst weeks had 0 extreme_greed_share_in_week (train base rate 0.0964807016778304) and mean_fear_greed_in_week below the train mean of 42.7779111120808 (33.40476190… (weak)
   - *Changed the conclusion:* Nothing strong enough to act on; it did not change the filters.
3. **Proposer agent** (AI agent) — Tried 6 filter(s) on Training, proposed 3. Each filter only changes position size. The strategy's own signals are never touched.
   - Flat when 7-day volatility is low (≤ 0.006409): H1 and H2 show vol_regime=low loses -9.325e-05 per decision (90% CI [-0.0001297, -5.438e-05]) while vol_regime=high earns 2.387e-05.
   - Flat when 7-day volatility is low (≤ 0.00753): Per H1 and H2, restricting full allocation to the top tertile of volatility (realized_vol_7d > 0.007530) avoids low-vol losses (-9.325e-05 per decision) and fo…
   - Half size when 7-day volatility is low (≤ 0.006409): A softer de-risking variant for H1 and H2 that scales down to 0.5 when realized_vol_7d <= 0.006409 rather than halting completely.
4. **Code: scoring** (Code) — Scored 6 rule(s) on Validation and Training folds. 3 of 3 agent filter(s) beat the original on Validation. Reference rules were scored the same way.
   - Half size when 7-day volatility is low (≤ 0.006409): +26.8 pp vs the original, own return +7.3%
   - Flat when 7-day volatility is low (≤ 0.006409): +58.2 pp vs the original, own return +38.8%
   - Flat when 7-day volatility is low (≤ 0.00753): +47.1 pp vs the original, own return +27.6%
   - Simple reference rule: -21.2 pp vs the original, own return -40.7%
5. **Code: health check** (Code) — Asked: unlucky or broken?. 45 of 45 validation 14-day blocks fall inside the training range [-0.1623, +0.1235]: a loss alone does not show the strategy broke.
6. **Critic agent** (AI agent) — Challenged 3 filter(s): rejected 2. The critic looks for leakage, overfitting and fragile samples. It can block a filter, not approve one.
   - Flat when 7-day volatility is low (≤ 0.006409): rejected — Due to a severe volatility regime shift between train and validation, this fixed train-median threshold leaves the gate off (0.0 allocation) 86.68% of the time and active only 13.32% of the time on v…
   - Flat when 7-day volatility is low (≤ 0.00753): rejected — On validation, the gate is almost always off: allocation_mix is 93.89% at 0.0 and only 6.109% at 1.0, resulting in an exposure of just 0.02147 and only 44 position switches across 15278 decisions (53…
   - Half size when 7-day volatility is low (≤ 0.006409): approved for one held-out test — While multiple agent trials were explored on train and walk-forward fold 2 had a wide CI including zero ([-0.1346, 0.2441]), walk-forward folds 1 and 3 had positive CIs ([0.09795, 0.5821] and [0.0554…
   - *Changed the conclusion:* The filter with the best Validation number (Flat when 7-day volatility is low (≤ 0.006409), +58.2 pp) was rejected by the critic, so it could not be selected.
7. **Code: selection rule** (Code) — Selected one filter for the held-out test. The rule was fixed before the run: beat the original with an interval above zero, beat cash, change something real, and not be rejected by the critic.
   - Selected: Half size when 7-day volatility is low (≤ 0.006409)
   - champion agent::vol_median_05_1 beats always-on and cash on validation and was not rejected by the critic
8. **Code: held-out test** (Code) — Opened the held-out test once. Beat the original by +27.3 pp (90% interval +15.3 to +36.2 pp). Worst drawdown 60.4% → 36.2%. Its own return was -28.9% — it still lost money.
   - *Changed the conclusion:* Selection did not become approval: the filter still lost money.
9. **Lane A arbiter** (Code) — Strategy verdict: KILL. held-out drawdown 60.4% is past the 40% cap and its net-return interval is entirely below zero. The agents' filter is not part of this verdict.
   - Applies to: the original strategy, always on

## Take away

**Strategy.** The analysis used this strategy's positions. Its definition and the file that generates them are listed here; this report itself contains no runnable code.
- Rule: Buy BTCUSDT when the 48-hour z-score of the close falls below -1; sell when it returns to 0.
- Parameters: `{"window_bars": 48, "entry_z": -1.0, "exit_z": 0.0, "bar": "1h", "side": "long or flat"}`
- Source: `A/kok_a/strategies.py (_mean_reversion, version meanrev-z48-v1)`

**Selected filter.** Exact settings of the selected filter. It was tested once on held-out data and is not approved.
- Half size when 7-day volatility is low (≤ 0.006409): When 7-day volatility is above 0.006409: full size. Otherwise: half size. Thresholds were set on Training data.
- Status: Selected for further testing · not approved
- Exact settings: `{"policy_id": "agent::vol_median_05_1", "family": "threshold_gate", "conditions": [{"feature": "realized_vol_7d", "op": ">", "threshold": 0.00640924015585452}], "allocation_when_true": 1.0, "allocation_when_false": 0.5, "thresholds_selected_on": "train"}`

**Evidence.**
- Full agent report (every claim linked to a tool result): `experiments/investigation_argon_meanrev.json`
- The one held-out test look: `experiments/frozen_look_btc-meanrev-48-demo.json`
- Half size when 7-day volatility is low (≤ 0.006409): scoring evidence: `ev_regime_perfo_df1c1d3a42`
- Half size when 7-day volatility is low (≤ 0.006409): scoring evidence: `ev_feature_grid_6306a31306`
- Half size when 7-day volatility is low (≤ 0.006409): scoring evidence: `ev_test_gate_tr_83c2982722`
- Unlucky or broken check: `ev_strategy_hea_312a17ad14`

Nothing here places orders. Any saved paper plan stays saved, not running.

---
*code (packages/research_agents/presentation.py); no new numbers, no new decisions.*
