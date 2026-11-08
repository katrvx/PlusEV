# Recorded research and challenge evidence

Preserved from the team README on 8 November 2026. This companion record keeps the original experiment narrative, numerical details, caveats and replay commands while the [main README](../README.md) presents the product tour. Paths in inline code are relative to the repository root.

**Real result on real data.** Binance spot BTCUSDT hourly bars, 2018-02-01 to 2026-10-31, with Fear & Greed. Research period 2018-02 → 2023-05, validation 2023-05 → 2025-02, test 2025-02 → 2026-10, scored once. The two demo strategies and their costs (10 bp + 1 bp) were fixed before the run. Agents ran on Gemini 4 Argon. Differences between a gate and the strategy as-is are in percentage points (pp):

| | Trend (`btc-trend-24-72-demo`) | Mean reversion (`btc-meanrev-48-demo`) |
|---|---|---|
| Strategy as-is | Research +276%; validation +134% (90% CI +14% … +413%) | Research −90%; validation −19% |
| Unlucky or broken? | 43 of 45 two-week validation blocks inside the research range, 2 above it | 45 of 45 inside the research range. That range comes from a period in which it lost 90% |
| Agent gates | 3 proposed, **all vetoed by the critic**. The best, "trade only when Fear & Greed > 28", beat as-is by 32 pp on validation. But sentiment had flipped (fear fell from 51% to 10% of the time), so the gate was on 97% of the time, and on the first research fold it trailed as-is by 48 pp | Champion: half size when 7-day volatility is below its research median. Validation +26.8 pp vs as-is (CI above zero), +7.3 pp vs cash, 3/3 research folds, critic approved. Holding a constant half size alone gives +11.1 pp |
| Test (one look) | Lane A arbiter: **INCONCLUSIVE** (intervals contain zero) | Gate vs as-is +27.3 pp (90% CI +15.3 … +36.2), drawdown 60% → 36%, but **net −28.9%: it still loses money**. Its average size was 0.55× as-is, so much of the gain is holding less of a losing strategy. Lane A arbiter: **KILL** for the strategy |

**What this test can and cannot claim** (found by our fourth adversarial review):

- **The test period was not unseen by us.** It overlaps the earlier two-year window (Nov 2024 → Oct 2026) we developed on, and there the agents had already proposed a similar idea: cut size in calm markets. So this is a pre-registered, single look at a period the team had seen. A clean test needs data after 2026-10-31.
- **Lane A's arbiter never scored the agent's gate.** Its KILL is for the strategy, chosen among Lane A's own candidates. Our selection rule required beating cash on validation, but we had not written down how a test result maps to a verdict. By the same bar, the gate fails on test (net −28.9%).
- **The critic acted as a selector.** It vetoed a sibling gate with the same condition (size 0 instead of 0.5), which scored higher on validation. Without that veto, the sibling would have been the champion.

The honest reading: the agents found a rule that reliably loses less, mostly by trading smaller. A strategy that loses money with or without it is a kill, not a fix. The single test look is in `experiments/frozen_look_btc-meanrev-48-demo.json`, taken after the report that chose the champion was committed.

**Organisers' challenge (the AgentVerse kit, `bench.py challenge`).** We pre-registered the plan in [`eval/challenge/kok-preregistration.md`](../eval/challenge/kok-preregistration.md) (committed 2327e45 before any run), then ran each strategy once with the gate on, and replayed the same revealed cases without it. Seed commitments matched; 0 errors; 300/300 paths each. Outputs: `eval/challenge/kok-mean_reversion/`, `eval/challenge/kok-trend/` (`paired.json` has every number).

| Kit challenge, 300 paths | Mean reversion | Trend |
|---|---|---|
| Gate on vs gate off, same paths | Gate better on 53, worse on 12, identical on 235 (sign test p = 3×10⁻⁷). Mean +0.93% of capital (90% CI +0.58 … +1.29), drawdown 1.1 pp smaller | Better 2, worse 8, identical 290 (p = 0.11): **untestable**. The 12–80-bar paths are shorter than its 72-bar warm-up, so it is flat on ~95% of them |
| Is that skill? | **No.** Cash beats the gated strategy on 56 paths vs 8 (p = 6×10⁻¹⁰). In the kit's all-in execution, half size rounds to flat, so the gate helps only by being out of the market more (exposure 0.50× of raw) | Cash beats it 10 vs 4 (p = 0.18) |
| Kit verdict vs buy-and-hold | 189 wins vs 111 (p = 8×10⁻⁶), but it beats cash on only 8 paths: it wins mostly by sitting in cash on falling paths. Without the gate: 185 vs 115 | 198 vs 102, same reason: almost always flat |

Same conclusion as on real data: the gate reliably loses less by holding less. It does not make the strategy worth running. A kit "beat buy-and-hold" verdict here comes from staying in cash, which is why we report the comparison with cash next to it.

Reproduce: `python3 scripts/kok_challenge.py challenge --strategy mean_reversion` runs the kit's `challenge` with the gated adapter, then `python3 scripts/kok_challenge.py replay --strategy mean_reversion --seed <revealed seed>` runs the same cases without the gate. To plug our agent into the kit directly, the adapter is `python3 -m packages.kit_adapter.kok --strategy {mean_reversion,trend} --mode {gated,raw}`.

**Show one control live (offline):** `python3 scripts/demo_controls.py` runs 4 controls: the sealed test split is refused to an agent; an invented number is rejected and the agent retries with copied numbers; a money-losing gate the AI critic approved is rejected by code; and a second look at the test split is refused even under a new name. `--only 2` runs one. It exits 1 if any control fails.

The agents propose and explain; **code computes every number and makes every decision.**
