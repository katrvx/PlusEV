# 11 · Demo and pitch

*"Judges score every team from the deck, so put your evidence there."* The deck is the primary deliverable. The live pitch is 4 minutes + 2 for questions, top 3 only.

## The one-liner

**Before you run it, we show you where it works. While it runs, we tell you whether it's broken or just in bad weather, and how long until you'd know.**

## Deck outline (12 slides, each with its rubric tag)

1. **Title.** +EV. One-liner. Team. Repo link, commit hash.
2. **The user and the decision.** *[Relevance 20%]* A trader, a bot, a 15% drawdown, three buttons. The forum thread: "how many live trades?" with the spread of answers. The practitioner stat: 8 of 11 interventions made it worse.
3. **What exists and where it stops.** *[Relevance / Ambition]* The table: regime tools know the market, drift tools know your bot, nobody joins them.
4. **What +EV does.** Two views on one tagged-trade table. Screenshot of the heatmap and of the verdict panel.
5. **Architecture: code vs. LLM.** *[Traceable reasoning 25%]* The diagram from [02](02-architecture.md) with every box marked. One sentence: the LLM never produces a number in a verdict. Why (three papers, one line each).
6. **The regime engine.** *[Traceable]* Features, all as-of bar open, no look-ahead test. Anonymised sentiment with lexicon baseline.
7. **The judge.** *[Traceable / Testing]* Conditional P&L → BH over *m* registered hypotheses → sealed holdout (receipt). Drawdown percentile, decomposition, e-process, "N more trades" as a labelled projection. One formula per method, no more.
8. **The swarm and the counts.** *[Ambition 15%]* "5 agents proposed 31, 4 refused as duplicates, 9 survived training, 6 confirmed on holdout." Pre-registration ledger screenshot.
9. **Evidence 1: X-ray out-of-sample.** *[Testing 25%]* E1 table: power on planted regime, false-confirmation rate vs. *q*, filter-vs-always with CI, at 1× and 2× costs.
10. **Evidence 2: Kill or Keep vs. the rules traders use.** *[Testing 25%]* E2 table: detection delay, false-kill rate, P&L preserved for DD-20, 3-loss, CUSUM, +EV, with intervals. E3: "N more trades" coverage. Honest-result clause if needed.
11. **Risk controls, shown.** *[Risk 15%]* The refused doubling-down, the pause, the override ledger tally, the hash-chained log with `verify` output. Paper only.
12. **Limits and next.** What we assume ([05 Part C](05-judge-and-stats.md)), memorisation-guard result, data licences (Binance non-commercial), what we'd do with a week.

Appendix: full E1–E5 tables, data manifest, prompts.

## Demo script (90 seconds, recorded as backup)

1. *(0:00)* Upload `backtest.csv` + paste the strategy description. Heatmap appears: green in low-vol/no-event, red in post-FOMC. "Six regimes confirmed out of thirty-one proposed."
2. *(0:25)* Switch to Live. Equity curve down 15%, two weeks. Regime bands over the price chart show the FOMC window in red.
3. *(0:40)* Verdict panel: *"Drawdown at the 78th percentile of your own backtest. 30 of 40 losses in post-event sessions, where the backtest also loses. Conditional on regime, live matches backtest. Edge alive: 78%. ≈35 trades to a 90% answer."*
4. *(1:00)* Click "increase size". Refused, reason shown, logged.
5. *(1:10)* Click "stop". Override ledger entry appears with the verdict at the time and "will be scored". Keep it running instead.
6. *(1:20)* Switch strategy to the dying bot. Retirement alarm fired 25 trades before the drawdown rule. Decomposition: signal term dominates. "This one is dead, not unlucky."
7. *(1:30)* Audit log → `verify` → chain OK.

## The pitch (4 minutes)

- **0:00–0:30 Problem.** The trader, the drawdown, the three buttons, the forum, the 8-of-11.
- **0:30–1:00 Gap.** Regime tools vs. drift tools. We join them.
- **1:00–2:30 Demo** (live, with the recording ready).
- **2:30–3:15 Evidence.** The three counts; E1 and E2 headline numbers with intervals; the honest clause if it applies.
- **3:15–3:45 Why the agent never decides.** One sentence on the three papers. "We let agents do what they're good at and keep them away from the verdict."
- **3:45–4:00 Limits and ask.** "Daily regimes only; Binance data non-commercial; here's what a week would add."

## Questions we expect and the answers

- **"How many things did you try?"** The ledger count. It's on slide 8 and in the log.
- **"Isn't regime analysis just overfitting?"** Pre-registered from the description before P&L, BH-corrected, confirmed on a sealed holdout with a receipt, episode count reported. And on noise strategies we confirm ≤ *q*. Slide 9.
- **"Why not let the LLM judge, it's smarter?"** 34–44% false claims in no-signal worlds, calibration slope 0.36, framing-sensitive. Slide 5.
- **"Does the sentiment feature actually add anything?"** E5. Whatever it says.
- **"What does 'N more trades' assume?"** That the future resembles the regime-matched backtest. It's labelled a projection; E3 shows its coverage.
- **"What's the e-process guarantee exactly?"** Per candidate, a no-edge stream reaches 1/α with probability ≤ α at any stopping time (Ville). Not FDR across strategies unless we apply e-BH, which we do for the X-ray hypotheses.
- **"Would you let it near your money?"** It never touches money. It makes the human's decision honest and recorded, and shows them what their own overrides cost.

## Visual rules

- Dark theme, trader-app look, one accent colour for "green regime", one for "red".
- Every number on a slide has an interval or a count next to it.
- No stock photos. Screenshots and tables only.
