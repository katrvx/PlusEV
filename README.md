# Barometer

**Before you run a trading bot, we show you where it works. While it runs, we tell you whether it's broken or just in bad weather, and how long until you'd know.**

AgentVerse 2026 · Finance Track (supported by Jane Street) · 7–8 November 2026 · UCL

---

## The problem

Algo traders don't know *when* their bot works. When it loses money they can't tell whether it's broken or just in bad conditions, so they kill good bots and keep dead ones. This is the single most-asked question on r/algotrading in 2026 ("how many live trades before I trust it?") and the answers range from "fifty" to "a thousand" to "go by feel". One team that tracked its own manual interventions found 8 of 11 made things worse.

Existing tools solve half of it each:

| Tools | Know the market | Know your bot | Say *why* | Say *how long until you know* |
|---|---|---|---|---|
| Regime APIs (getregime, TradingView scripts) | ✅ | ❌ | ❌ | ❌ |
| Drift monitors (Algo Studio, AlgoTradingHub) | ❌ | ✅ | ❌ | ❌ |
| **Barometer** | ✅ | ✅ | ✅ | ✅ |

Regime tools tell you what the market is doing. Drift tools tell you your bot changed. Barometer is the first to put your bot and the market in the same table.

## What it does

One data model: **every trade (backtest or live) tagged with the regime it happened in** (volatility, trend, liquidity, scheduled event, LLM-read news sentiment). Two views on it:

**1. X-ray** — before you trust it. Backtest trades → heatmap of where the bot makes and loses money → the bot's *operating envelope*, validated out-of-sample with multiple-testing correction. *"Works in calm, mildly bullish, no-event days. Dies in the two days around rate decisions."*

**2. Kill or Keep** — while it runs. Live trades → three answers:
- Is this drawdown within what the backtest implied?
- If not: is it **execution** (costs rose), **signal** (edge faded), or **regime** (the market is in weather the backtest barely saw)?
- **How many more trades until we know**, with an interval.

Plus an **Override Ledger**: every manual intervention logged and scored afterwards.

## How the agents fit (and why they never decide)

A swarm of agents with different lenses (volatility, macro, sentiment, liquidity, devil's advocate) **proposes** regime hypotheses *before seeing any P&L*. Parallel agents **label** headlines (anonymised, to block memorisation). Agents **explain** verdicts in plain language. **One frozen, deterministic judge decides everything**: tests every hypothesis, corrects for the total number tried, confirms survivors on a sealed held-out window, runs the sequential test for live decay. The LLM has zero power over any number in the output.

This split isn't a hedge, it's the thesis. Three papers published in the last eight weeks show that LLM research agents claim predictability in no-signal worlds 34–44% of the time *when allowed to judge*. We let them do what they're good at and keep them away from the verdict. See [docs/06-agents-and-swarm.md](docs/06-agents-and-swarm.md).

## How we prove it works

We run strategies with **planted truth** on real price history: one with a live edge, one that is pure noise, one whose edge dies at a known time *T*. Barometer sees only the trade stream. We measure how much earlier it catches dead bots and how much less often it kills live ones than the "stop at 20% drawdown" rule traders actually use, and whether the X-ray's green regimes stay green out-of-sample after costs. Honest result either way. See [docs/07-evaluation-protocol.md](docs/07-evaluation-protocol.md).

## Docs

| # | Doc | What's in it |
|---|---|---|
| 01 | [Problem and user](docs/01-problem-and-user.md) | Who it's for, the decision they get wrong, evidence from forums |
| 02 | [Architecture](docs/02-architecture.md) | Components, data flow, what's code vs. what's LLM |
| 03 | [Tech stack](docs/03-tech-stack.md) | Every library, why it, version, licence |
| 04 | [Regime engine](docs/04-regime-engine.md) | Regime definitions, pre-registration, no-look-ahead rules |
| 05 | [Judge and statistics](docs/05-judge-and-stats.md) | The maths: conditional P&L, OOS validation, drift, decomposition, "N more trades", sequential retirement |
| 06 | [Agents and swarm](docs/06-agents-and-swarm.md) | ADK design, schemas, anonymisation, memorisation guard |
| 07 | [Evaluation protocol](docs/07-evaluation-protocol.md) | Planted truth, metrics, benchmarks, sealed holdout |
| 08 | [Risk controls and audit log](docs/08-risk-controls-and-audit-log.md) | Limits in code, hash-chained log, the control shown live |
| 09 | [Data sources](docs/09-data-sources.md) | Every dataset with licence |
| 10 | [Build plan](docs/10-build-plan.md) | Hour-by-hour, roles, scope guards |
| 11 | [Demo and pitch](docs/11-demo-and-pitch.md) | Deck outline mapped to the rubric, 90-second demo script |
| 12 | [References](docs/12-references.md) | Papers, products, threads |

## Judging rubric → where we score

| Criterion | Weight | Barometer |
|---|---|---|
| Traceable reasoning | 25% | Every verdict is a chain: raw prices → regime tags (code) → conditional stats (code) → explanation (LLM, quoting the numbers). Hash-chained log. |
| Testing on unseen data | 25% | Planted-truth strategies, sealed held-out window, real costs, bootstrap intervals, benchmark = the rules traders use today. |
| Risk controls and oversight | 15% | Size cap and pause enforced in code, human confirms resumption, doubling-down blocked. Shown live. |
| Relevance and impact | 20% | A named user (retail/small-fund algo trader), the failure on screen: killing a live bot in a bad week. |
| Ambition and technical quality | 15% | Strategy-conditional regime analysis + anytime-valid sequential decay detection + LLM swarm under a frozen judge. |

## Status

Docs only. Code starts Saturday 15:30. Build order in [docs/10-build-plan.md](docs/10-build-plan.md).

## Team

Kate Baitaliuk (lead) and team · AgentVerse 2026

## Licence

MIT. Data licences are listed per source in [docs/09-data-sources.md](docs/09-data-sources.md); some market data is non-commercial only.
