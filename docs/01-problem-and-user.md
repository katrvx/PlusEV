# 01 · Problem and user

## The person

**A retail or small-fund algorithmic trader** with a backtested strategy running live, or about to. Typically runs 1–5 bots on crypto, futures or US equities through a broker API, has a backtest with a few hundred to a few thousand trades, and watches the live P&L every day.

The Finance track brief says: *"Pick one person who runs, regulates or relies on a financial system, find a decision they get wrong or make too slowly, and build an agent that helps."* The brief's own example is "a trader testing a hunch". This is that person, one step later: the hunch passed the backtest and is now live.

## The decision they get wrong

The bot is in a drawdown. The trader must choose: **keep running, cut size, or kill it.**

They get it wrong in both directions:

- **Kill a good bot.** A drawdown that is well within what the backtest implied triggers panic. The strategy would have recovered. The trader has now paid for the losses and forfeited the recovery.
- **Keep a dead bot.** The edge decayed (crowding, regime change, broker changed fills) but the trader keeps waiting for the "normal" recovery that never comes.

And they get it wrong **slowly**: the forum consensus is to wait "hundreds" of trades, which can mean months of either bleeding or missed profit.

## Evidence this is real (what traders say)

From r/algotrading, r/quant, r/Trading and practitioner write-ups, 2024–2026 (full links in [12-references.md](12-references.md)):

- Thread, January 2026: *"How many live trades before I trust it and stop intervening?"* Answers: "hundreds", "50–100", "1000 over 3–4 months", "within 1 SD for 30–50 trades is fine, beyond 2 SD means regime change or a backtest that missed something". **No agreed method.**
- A team's first live month (written up in 2026): backtest Sharpe 2.1 → live 0.9. **11 manual interventions in January, 8 made things worse**, ≈$1,200 lost to overrides on a small account. By March they were down to 1 intervention after adding a 4-hour cooling-off rule.
- r/algotrading "things you wish you knew": *"Backtesting usually doesn't match live"*; one trader went from ≈90% win rate in backtest to ≈20% live and could not tell overfitting from bad luck.
- r/algotrading snapshot, May 2026: separate active threads on "how many live trades are enough", "discretionary override during drawdowns", "retire or re-optimise", "walk-forward vs equity-curve", "how to separate overfitting from a good strategy".
- Practitioner guide (Breaking Alpha, 2025) lists the full statistical toolkit for decay detection — rolling Sharpe, CUSUM, Chow test, HMM regimes, bootstrap CIs — and concludes: *build your own dashboard.*

## What exists today and where it stops

| Product | Does | Doesn't |
|---|---|---|
| getregime.com | Labels crypto market bull/bear/chop; suggests pausing bots in hostile regimes. | Never sees your strategy. |
| Build Alpha | 215 regime signals usable as filters; walk-forward tests. Desktop, manual. | No breakdown of *your* P&L by regime; no live monitoring; no news. |
| SentimenTrader | Backtester with proprietary sentiment indicators. | Can't upload an existing backtest; no regime attribution; no live monitoring. |
| Algo Studio (MT5) | CUSUM drift alert live vs backtest; can auto-halt. | No cause, no "how long until you know", no regime. |
| AlgoTradingHub | Recomputes backtest metrics on live trades; AI assistant can "look for drift". | No statistical test described, no cause, no regime. |
| TradingView regime scripts | Chart says trending/ranging. | Market only. |

**The pattern:** everyone classifies the *market*. Nobody classifies *your strategy against the market*. The regime tools don't know your bot; the drift tools don't know the regime.

## What Barometer answers

1. **Where does this bot work?** P&L by regime, validated out-of-sample. (X-ray)
2. **Is this drawdown normal?** Compared to the backtest's own drawdown distribution. (Kill or Keep)
3. **If not, why?** Execution vs. signal vs. regime, with the evidence. (Kill or Keep)
4. **How many more trades until we know?** With an interval. (Kill or Keep)
5. **Are my own interventions helping?** Override Ledger.

## The failure handled on screen (rubric: relevance and impact, 20%)

A bot is down 15% over two weeks. The trader opens the kill switch. Barometer: *"This drawdown is 1.2σ from your backtest's drawdown distribution. 30 of your 40 losing trades fell in the three sessions after the 29 Oct rate decision; your strategy's envelope shows it loses in every event window in the backtest too. Conditional on regime, live performance matches backtest. Probability the edge is alive: 78%. Trades until a 90% answer: ≈35. Historically, intervening here would have cost you 2.3%."* The trader keeps the bot. Second case: a bot whose edge genuinely died; Barometer flags it 25 trades before the drawdown rule would have.

## Impact, honestly stated

We will not claim a dollar figure for the retail market. What we can show: on strategies with planted truth, how many fewer good bots get killed and how many fewer dead bots get kept versus the rule traders use today, after costs. That number is the impact claim.

## Out of scope

- Generating strategies or alpha. Barometer judges, it does not invent.
- Executing trades. Paper mode only; the human presses every button that moves money.
- High-frequency strategies (sub-second). Our regime tags are daily/hourly.
