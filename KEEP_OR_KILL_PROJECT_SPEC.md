# Keep or Kill

**Project specification | AgentVerse Finance track | 7 November 2026**  
**Tagline:** *Don't rewrite the strategy. Discover when to trust it.*  
**Stage:** Hackathon MVP specification; not a claim of validated alpha.

---

## 1. The idea in one paragraph

Quantitative trading agents and independent researchers can generate and backtest strategies, but conventional backtest summaries hide *when* a strategy works. A strategy with negative average returns might contain valuable conditional information: it may perform well when volatility is falling and momentum is positive, or fail when liquidity deteriorates and news turns adverse. **Keep or Kill** is an AI-assisted strategy-supervision layer that ingests **existing, unchanged strategies** and their historical signals/trades, reconstructs the market conditions observable at each decision, discovers performance strengths and failure modes, and proposes *when to activate, reduce, combine, monitor, or switch off* those strategies. Deterministic statistical models test these proposals on unseen data, with transaction costs and strict information cutoffs. A human can approve a frozen policy for a **14-day, paper-only champion–challenger evaluation**.

### One-sentence hackathon pitch

> **Keep or Kill is an AI-powered research supervisor for trading strategies that uses historical market regimes, sentiment and news to discover when an existing strategy has an edge, then independently tests whether activating or disabling it under those conditions actually improves risk-adjusted returns.**

### Thirty-second pitch

> A strategy can look terrible overall and still be excellent in a particular market. Today's backtest dashboards give you a Sharpe ratio, but not a rigorous answer to *where the edge exists, whether you could have recognised it at the time, and whether to keep funding the strategy*. Keep or Kill reconstructs the market context around each historical trade, finds conditional strengths and weaknesses, uses AI agents to investigate the economic reasons, and backtests a strategy-selection overlay without changing the strategy itself. It compares the overlay against always-on strategies and simple rules on unseen data, then prepares a two-week paper-trading test. Every decision is evidence-backed and reversible.

## 2. Problem, customers, and value

**Problem:** Strategy creators routinely confuse three very different situations:

1. **Unlucky:** A valid strategy experiences a plausible short-term drawdown.
2. **Condition-dependent:** A strategy works in identifiable conditions but not in others.
3. **Broken:** Its assumed edge no longer holds, its backtest is flawed, or actual costs erase the advantage.

A simple aggregate return/Sharpe chart cannot distinguish these reliably. Manually adding contextual datasets, searching for regime effects, and building *point-in-time* strategy gates is slow and easy to overfit.

**Primary user for the demo:** an independent systematic trader or small quant research team managing 2–10 strategies.  
**Future users:** multi-strategy quant shops, trading-agent platforms, systematic portfolio managers, AI trading research products.  
**User decision:** keep allocating to a strategy, activate it only in selected conditions, reduce its weight, combine it with a complementary strategy, monitor it, or retire it.

**Why it matters:** It may salvage useful conditional strategies while preventing money from being allocated to systems whose assumptions have stopped holding. It also gives a transparent account of *why* a gate fired rather than presenting an opaque AI instruction to trade.

### What this is NOT

- Not an LLM that rewrites sophisticated alpha models or autonomously invents profitable trading algorithms.
- Not an AI that forecasts price directly from news headlines and places real trades.
- Not a promise that an underperforming strategy can always be rescued.
- Not an agent marketplace or paid-data procurement product for the MVP.
- Not a claim that 14 days of paper trading is statistically sufficient to certify profitability.

**Core design constraint:** The **base strategy is immutable** throughout the experiment. Keep or Kill changes only a *supervisory allocation/activation policy*, never the underlying signal-generation algorithm.

## 3. Product experience

### User journey

1. **Upload** an existing backtest or connect a strategy. Minimum useful inputs: timestamped target positions/signals, instrument, timeframe, original strategy assumptions, and portfolio/equity records. Trades-only files can support diagnosis but often cannot support faithful alternative gating simulations.
2. **Reconstruct market context:** join every decision with price/volume, trend, volatility, funding where relevant, sentiment, and available historical news, all using point-in-time availability.
3. **Inspect strengths and weaknesses:** heatmaps and tables show returns, drawdowns, turnover, and sample counts by bull/bear/sideways, high/low volatility, sentiment, liquidity, and combinations.
4. **Investigate:** an agent proposes falsifiable reasons for differences, requests statistical tools, and cites concrete dated evidence rather than producing fictional performance numbers.
5. **Propose a policy:** *activate Strategy A when the classifier estimates favourable conditions; reduce B in high-volatility/high-cost conditions; prefer cash otherwise.* No changes to either strategy.
6. **Challenge it:** run a simple rule baseline, a quantitative gate, and the agent-proposed gate under identical walk-forward splits; account for fees, slippage, funding, strategy switching and uncertainty.
7. **Decide:** recommend KEEP / ACTIVATE CONDITIONALLY / REDUCE / COMBINE / MONITOR / KILL, or **INCONCLUSIVE**.
8. **Paper-test:** freeze the champion and challenger policies, monitor both in parallel for 14 days, and compare realised results with the *pre-registered* expected-outcome distributions.

### Example narrative (hypothetical, NOT measured)

- A BTC momentum strategy has **−8% net return** overall in its historical backtest.
- Historical diagnosis shows most profits occurred in **upward-trending, low-volatility** conditions, while losses clustered during **volatile sideways/bear markets**.
- A news analysis identifies frequent adverse macro/regulatory stories during some losses. That is *contextual evidence*, not proof of causation.
- A diagnostic agent hypothesises: “A lagged trend/volatility filter may improve this strategy by avoiding unreliable periods.”
- The quant evaluator learns the filter only on training/validation periods. The frozen gate is tested on later unseen data against always-on momentum and a naive moving-average rule.
- **If** the gate improves after-cost results without materially increasing tail risk, recommend **ACTIVATE CONDITIONALLY**. Otherwise retain **MONITOR** or **KILL**. The dashboard shows actual measured results, not these illustrative numbers.

### User-facing screens

1. **Strategy Import:** upload example `.parquet` / `.csv`, set execution assumptions, validate schema.
2. **Strategy Health:** overall performance, original backtest assumptions, realised-vs-expected deviations, cohort sample sizes.
3. **Market Context Explorer:** historical equity curve with aligned trend, volatility, sentiment and news events; regime-performance heatmap.
4. **Agent Investigation:** timeline of evidence, hypotheses, tool calls, rejected explanations and confidence limitations.
5. **Champion vs Challenger:** always-on, rule-gated and model-gated equity curves; net metrics, uncertainty, turnover, out-of-sample windows.
6. **Decision Report:** verdict, supporting evidence, conditions, limitations, and the frozen paper-test protocol.

## 4. Key differentiator

**Most quant backtest tools ask:** *How did the strategy perform?*  
**Keep or Kill asks:** *When did it perform, what information was available before those trades, can a supervisor detect favourable conditions ahead of time, and does that supervisor improve a real financial decision?*

Two layers are deliberately separate:

- **Ex-post diagnostics:** describe which *historical* regimes coincided with good/bad strategy outcomes. This is allowed to use subsequent returns for labeling/descriptive analysis, but its result is not automatically actionable.
- **Ex-ante gate:** a policy trained only on past observations decides activation from **features known at decision time**. Only *this* layer may be used in unseen backtests or paper trading.

An oracle gate that identifies future bull markets is an invalid benchmark, not an achievement.

## 5. Mathematical framing

Let strategy \(i\) provide target exposure \(s_{i,t}\), and let \(x_t\) be market-context features **available by time \(t\)**. The supervisor produces a constrained allocation \(w_{i,t}=g_\theta(x_t, i)\).

For a basic long-only demonstration, \(w_{i,t}\in\{0,0.5,1\}\); optionally include a cash fallback. Effective target exposure is \(q_{i,t}=w_{i,t}s_{i,t}\). Evaluate orders/fills for the **next executable interval**, not the bar whose final price produced \(x_t\).

A one-asset simplified P&L equation (for intuition only) is

\[
R_{t+1}^{\mathrm{net}} = q_t R_{t+1}^{\mathrm{asset}} - c\,|q_t-q_{t-1}| - f_{t+1}(q_t),
\]

where \(c\) represents execution cost, and \(f\) funding/borrow costs where applicable. The actual implementation uses an execution simulator to handle entry/exit orders, fills, sizing, and shared capital. **Do not** multiply the original strategy’s already-net P&L by an on/off mask: toggling creates additional trades and costs.

### Core research objectives

- Estimate conditional performance \(E[R_i\mid X_t]\), with uncertainty.
- Compare the unchanged base strategy against gating policies net of costs.
- Test whether regime selection survives walk-forward out-of-sample periods.
- Penalise turnover, drawdown, exposure and unnecessary switching.
- Distinguish plausible short-term luck from evidence of model or execution failure.

**Operational decision policy:** there is no single universal statistical threshold for “kill.” Use explicit, pre-registered risk and evidence criteria and allow **INCONCLUSIVE** when power is insufficient.

## 6. Technical architecture

```text
        EXISTING STRATEGIES (IMMUTABLE)
    CSV/Parquet trades, target positions, signals
                      |
                      v
       Import / Normalize / Validate / Hash
                      |
              ┌───────┴────────┐
              v                v
       Market OHLCV        Sentiment / News
       Funding / Vol       as-of availability
              └───────┬────────┘
                      v
       POINT-IN-TIME FEATURE STORE
        DuckDB + Parquet + Polars
                      |
             ┌────────┴────────┐
             v                 v
      Quant Evaluator      Research Agents
      regime models       diagnose + hypothesise
      stats + backtest    tools + evidence only
             └────────┬────────┘
                      v
         SUPERVISORY GATE CANDIDATES
         always-on | rule | LightGBM
                      |
                      v
       WALK-FORWARD CHAMPION / CHALLENGER
       cost-aware execution, holdout, stress
                      |
                      v
       DECISION REPORT + HUMAN APPROVAL
                      |
                      v
       14-DAY PARALLEL PAPER EVALUATION
```

### Stack decisions

| Component | MVP choice | Reason |
|---|---|---|
| Backtesting and risk metrics | `vectorbt`, NumPy | Fast prototyping of fixed strategies and switching overlays. Ensure next-bar execution and correct costs. |
| Research framework | **Microsoft Qlib** as optional adapter / comparison | Strong experiment and portfolio research workflows. Not required to parse custom crypto feeds on day 1. |
| Existing agentic quant research | **Microsoft RD-Agent** as reference / optional input producer | Its primary job is factor/model generation; Keep or Kill is *not* rebuilding or depending on that loop. |
| Market/regime model | `lightgbm`, `scikit-learn` | Predict conditional strategy quality; compare with transparent rule baseline. |
| Regime diagnostics | `scikit-learn` first; `hmmlearn`, `ruptures` later | Avoid fragile complexity before the basic evaluation works. |
| Statistics | `scipy`, `statsmodels`, `arch` bootstrap | Confidence intervals, drawdown tests, structural stability, block resampling. |
| Data pipeline | `polars`, `duckdb`, `pyarrow` | Fast local feature joins, reproducible Parquet artifacts. |
| News semantic features | FinBERT or LLM batch labeller | Classify tone/event topic; provide text evidence and confidence limitations. |
| AI research orchestration | `PydanticAI` + Pydantic schemas | Typed hypotheses, registered tools, auditable outputs. |
| Backend | FastAPI | Submit runs, list experiments, inspect evidence. |
| UI | Next.js + Tailwind + Recharts | Interactive demo dashboard. |
| Experiment storage | DuckDB + Parquet + run manifests | Simple local deployment, source hashes, reproducibility. |
| Tests | `pytest`, `hypothesis` | Catch temporal leaks, incorrect fills and evaluation errors. |

**Deliberate omissions:** no live brokerage integration, no smart contracts, no general strategy code generation, no data purchasing, no LLM deciding orders directly. These are distractions for the Finance track MVP.

### Source documentation

- Microsoft Qlib: https://github.com/microsoft/qlib
- RD-Agent: https://github.com/microsoft/RD-Agent
- vectorbt portfolio interface: https://vectorbt.dev/api/portfolio/base/
- PydanticAI: https://pydantic.dev/docs/ai/core-concepts/agent/
- Binance public data: https://github.com/binance/binance-public-data
- Alternative.me sentiment API and attribution: https://alternative.me/crypto/fear-and-greed-index/
- GDELT DOC 2.0: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- FinBERT: https://huggingface.co/ProsusAI/finbert

## 7. Data and point-in-time correctness

### Primary MVP dataset

- BTCUSDT, 1-hour bars; optionally ETHUSDT.
- Download historical market data from the Binance public archive; choose **either spot or futures** and match the strategy's actual execution venue. If using futures, account for funding, mark-price behavior and margin assumptions.
- Generate two or three **frozen demo strategies** (e.g., trend following, mean reversion, breakout), or import a real existing strategy's timestamped signals. Don't pretend synthetic examples are independently discovered alpha.
- Start with price/volume derived features: 24h/7d lagged momentum, realised vol, ATR, volume z-score, drawdown, rolling trend, and optionally funding.
- Add daily Alternative.me Fear & Greed with source attribution; use a conservative next-day availability rule unless exact historical publication times can be verified.

### News / semantics

- **Day 1:** a small, curated, timestamped set of news items (for selected market windows) with URL, first-seen timestamp, source and content hash. Semantic labels include `risk_on_off`, `regulatory`, `macro`, `exchange_failure`, `institutional_flows`, and polarity.
- **Day 2 / optional:** batch-extract with FinBERT or an LLM; aggregate only news **available before the decision cutoff**. Keep source links attached to output.
- GDELT DOC 2.0's documented article search window is limited (historically about 3 months), so **do not promise a five-year news backfill from its DOC API**. For old periods use a legitimately accessible dated archive, prepackaged sample, or omit news from that experiment.
- Avoid using revised article text or later-edited headlines as if they were contemporaneous. A publication timestamp alone may not prove first availability.

### Required data schema (hourly rows, UTC)

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class StrategySignal(BaseModel):
    strategy_id: str
    symbol: str
    decision_time: datetime     # UTC, signal computed only from closed bars
    target_position: float = Field(ge=-1.0, le=1.0)
    strategy_version: str       # immutable version / code hash

class MarketContext(BaseModel):
    decision_time: datetime
    symbol: str
    momentum_24h: float | None = None
    realized_vol_7d: float | None = None
    volume_zscore: float | None = None
    funding_rate: float | None = None
    fear_greed: float | None = None
    news_sentiment: float | None = None
    data_max_available_at: datetime

class GateDecision(BaseModel):
    strategy_id: str
    decision_time: datetime
    allocation_multiplier: Literal[0.0, 0.5, 1.0]
    policy_id: str
    rationale_evidence_ids: list[str]
```

Every joined row must pass `data_max_available_at <= decision_time`; fill missing data conservatively and emit coverage percentages. No forward-fill across a pre-publication boundary. Archive raw inputs with data snapshot hashes. Binance notes that its spot archive timestamps changed units in 2025, so the ingestion layer must normalise time units explicitly.

## 8. Quant research and evaluation engine

### Inputs and labels

The required base-strategy artifact is a **target-position series or a reproducible signal generator**. A list of completed trades is useful but cannot always recreate alternate entries/exits with correct costs. For demo strategies, regenerate positions deterministically from saved inputs and code hashes.

For a decision at the close of bar `t`, use features observed up to `t`; execute at the next eligible open (`t+1`) with explicitly assumed fees and slippage. Targets for model training can be the *subsequent* strategy opportunity return over a defined horizon, with careful treatment of overlapping labels. If the base signal is flat, there is no opportunity to gate.

### Models to compare (all run on identical data)

1. **Always on:** original unchanged strategy.
2. **Always off / cash:** useful minimum benchmark.
3. **Simple rule:** lagged market trend and volatility gate with a small fixed parameter set.
4. **LightGBM meta-model:** estimates conditional strategy performance; probability calibrated on validation data, converted to 0/0.5/1 via *preselected* thresholds.
5. **Agent-recommended gate:** the agent picks from an **allowlisted** family of interpretable rules/features based on training evidence, not unrestricted hindsight. Evaluate it independently.
6. **Optional multi-strategy allocation:** select among Strategy A, B, or cash while respecting total exposure and switching costs.

### Time-series design

For a hackathon with enough history, use an illustrative scheme:

- Train: first 60% of chronology.
- Validation/model selection: next 20%.
- **Untouched test:** final 20%, evaluated only after policies and thresholds are frozen.
- Within train/validation, use rolling or expanding walk-forward folds. Purge/embargo around overlapping label horizons when needed.
- Keep timestamps and data source snapshots fixed so the result is reproducible.

For an agent that explores many hypotheses, record every attempted policy, not only the winning one. Flag multiple-comparison risk, use simple baselines, and avoid claiming statistical significance from a few trades.

### Evaluation metrics

- **Net return** with realistic fees, spread/slippage, funding if applicable, and switching costs.
- **Sharpe ratio** (appropriate annualisation) and **Sortino**; don't rely on Sharpe alone.
- **Maximum drawdown, tail loss / CVaR**, exposure, average holding time.
- **Turnover and number of switches**, participation/cost assumptions.
- **Conditional return by regime** with counts and uncertainty intervals.
- **Δ net performance vs always-on**, vs simple rule baseline, and vs cash.
- **Coverage:** fraction of market/strategy decisions with valid context features.
- **Ablation:** market-only gate versus market + news/sentiment gate.
- **Robustness:** rolling windows, different fees/slippage, block bootstrap, shuffled-news/placebo features.

Important: bootstrap the relevant return series/blocks rather than IID single trades when returns are autocorrelated. Bootstrapped intervals do not fix selection bias caused by scanning hundreds of strategies.

### Bad luck vs broken model

Use the original strategy's training-period return distribution, risk profile and cost assumptions to generate a predictive range for later performance. If a 14-day result falls in a plausible tail, the honest conclusion may be **inconclusive**. If costs, regime frequencies or exposures materially diverge, identify which *assumption* changed. A poor result alone is not enough to infer structural breakdown.

## 9. Agent roles and constraints

All **research agents can inspect evidence and request approved tools**. They do not place trades or change strategies. Model output is never used as a direct order.

### Agent 1: Diagnostic Analyst

**Input:** backtest summary, regime-conditioned metrics, source-covered historical context, statistical tests.  
**Output:** ranked hypotheses of where/why the strategy works or fails, evidence IDs, caveats, and tests to run.  
**Tools:** `get_regime_performance`, `get_cost_attribution`, `get_strategy_health`, `fetch_news_context`, `run_bootstrap`.

### Agent 2: Context and News Analyst

**Input:** dated news records, sentiment series, market-event windows.  
**Output:** structured event themes, changes in tone, relevant citations; suggests lagged features.  
**Constraint:** no inference that an observed news correlation proves a causal relationship.

### Agent 3: Gate Researcher

**Input:** prior hypotheses and **training/validation only** model results.  
**Output:** allowlisted policy proposal with explicit activation thresholds, expected benefit, risk limits, and a falsification test.  
**Tools:** `evaluate_rule_gate_train`, `evaluate_model_gate_train`, `compare_baselines`.

### Agent 4: Independent Critic

**Input:** candidate policy, lineage, trial log, metrics.  
**Output:** leakage concerns, overfit risks, fragile sample counts, counterexamples, required changes, or approval for frozen test.  
**Constraint:** cannot silently change thresholds after inspecting holdout performance.

### Deterministic arbiter (NOT an LLM)

The arbiter executes the approved evaluation scripts and applies constraints: no real orders, maximum position size, max strategy exposure, no disallowed dataset, no future information, strict experiment versioning. It can return **INCONCLUSIVE** even if agents are confident.

### Typed hypothesis contract

```json
{
  "strategy_id": "btc-momentum-v1",
  "hypothesis": "Trend persistence plus falling volatility improves next-period strategy net returns",
  "feature_requirements": ["lagged_trend_24h", "lagged_vol_7d"],
  "proposed_policy": {
    "family": "threshold_gate",
    "target_allocation": [0, 0.5, 1],
    "thresholds_selected_on": "validation_only"
  },
  "evidence_ids": ["regime_42", "bootstrap_07"],
  "evaluation_plan": {
    "baselines": ["always_on", "cash", "simple_rule"],
    "primary_metric": "net_return_after_costs",
    "holdout_policy": "frozen_one_time"
  }
}
```

## 10. API contract

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/strategies/import` | POST | Upload immutable signals/trade history and metadata |
| `/api/strategies` | GET | List available strategies, coverage, versions |
| `/api/experiments` | POST | Start a diagnosis/evaluation on specified snapshots |
| `/api/experiments/{id}` | GET | Read status, metrics, data provenance, artifacts |
| `/api/experiments/{id}/regimes` | GET | Conditional performance heatmaps |
| `/api/experiments/{id}/investigations` | GET | Agent hypotheses, tool calls and critique log |
| `/api/experiments/{id}/comparison` | GET | Always-on vs rules vs model vs agent overlay |
| `/api/experiments/{id}/report` | GET | Structured auditable final recommendation |
| `/api/paper-tests` | POST | Record approved frozen 14-day paper-test plan |
| `/api/paper-tests/{id}` | GET | Monitor independent champion/challenger runs |

Long-running research jobs can be locally queued using an in-process worker for the demo; for real deployment use a proper queue/worker (e.g., Redis/RQ or Celery). Do not block the web request for model training.

## 11. Repository layout

```text
keep-or-kill/
├── README.md                     # public-facing pitch, setup, demo
├── AGENTS.md                     # parallel coding agents + boundaries
├── pyproject.toml
├── docker-compose.yml            # optional local services
├── apps/
│   ├── api/                      # FastAPI routes
│   └── web/                      # Next.js UI
├── packages/
│   ├── contracts/                # Pydantic schemas, JSON schemas
│   ├── ingestion/                # price, sentiment, news loaders
│   ├── feature_store/            # point-in-time joins, lineage
│   ├── strategies/               # immutable example signals
│   ├── quant/                    # returns, costs, vectorbt, walk-forward
│   ├── meta_policy/              # rule gate, LightGBM gate
│   ├── research_agents/          # diagnostic, context, gate, critic
│   ├── evaluation/               # metrics, placebo tests, decision logic
│   └── paper/                    # paper-only shadow runner
├── data/
│   ├── raw/                      # external data snapshots (gitignored)
│   ├── processed/
│   └── fixtures/                 # tiny reproducible public sample
├── experiments/                  # run manifests, hashes, model outputs
├── tests/
│   ├── test_no_future_data.py
│   ├── test_execution_lag.py
│   ├── test_switching_costs.py
│   ├── test_holdout_isolation.py
│   └── test_policy_baselines.py
└── scripts/
    ├── fetch_market_data.py
    ├── build_features.py
    ├── run_backtests.py
    └── demo_seed.py
```

## 12. Build plan: three developers with coding subagents

Having three high-usage coding subscriptions helps with **parallel code production, testing and review**; it does **not** automatically grant unlimited production LLM API inference. Use low-volume runtime LLM calls and deterministic/local features where possible.

### Developer A — Data and Quant Engine

**Owns:** `packages/ingestion`, `feature_store`, `strategies`, `quant`, `evaluation`.  
**Tasks:** build market ingestion + reproducible signals; make point-in-time feature joins; implement next-bar execution, costs, regime heatmaps, always-on/rule/model benchmarks, chronological splits, and metrics.  
**Subagent reviewers:** timestamp leakage audit, execution-cost audit, statistical assumptions audit.  
**Acceptance:** `pytest` catches intentionally injected future leakage and shows realistic switching costs.

### Developer B — Agents and Intelligence

**Owns:** `packages/research_agents`, `meta_policy`, news feature extraction.  
**Tasks:** implement PydanticAI structured reports, allowlisted tool registry, diagnostic/context/gate/critic workflows, FinBERT or small-batch LLM news labelling, LightGBM meta-predictor.  
**Subagent reviewers:** hallucinated evidence, hypothesis/test separation, news timestamp validation.  
**Acceptance:** every claim references stored evidence IDs; no LLM edits base strategy or sees untouched holdout labels.

### Developer C — Product and Integration

**Owns:** `apps/api`, `apps/web`, demo/paper-test interface, docs.  
**Tasks:** strategy upload, dashboard, regime heatmap, agent investigation timeline, original-versus-gated equity curves, report, 14-day experiment configuration.  
**Subagent reviewers:** API contract validation, UI smoke tests, demo walkthrough.  
**Acceptance:** end-to-end demo works from checked-in sample files without paid API credentials (agent report may have deterministic fixture fallback).

**Coordination protocol:** agree on schemas before coding; each lane owns separate directories; use branches/worktrees, pin Python/JS deps, exchange fixture JSON/Parquet in the first hours; integrate at least twice before final demo. No three-agent simultaneous edits to one file.

### Suggested ~48-hour priority sequence

| Phase | Must have |
|---|---|
| 0–6h | Frozen strategy CSV schema; fixtures; prices ingestion; project skeleton; contracts |
| 6–16h | Correct always-on simulator; regime joins and heatmap; first tests; simple rule gate |
| 16–26h | Chronological split; LightGBM policy; agent diagnostics with evidence; comparison endpoints |
| 26–36h | News/sentiment as-of feature where valid; UI; critic; risk checks |
| 36–44h | Freeze holdout; run real measured comparison; ablations; package demo |
| 44–48h | Documentation, README, reproducible run commands, pitch/demo rehearsal |

**Scope cut rule:** if ingestion, execution timing and holdout validity are not reliable by mid-hackathon, drop news and HMM before dropping scientific correctness.

## 13. MVP definition and acceptance tests

**MVP is complete when:**

- [ ] Two unchanged strategies can be imported or reproduced deterministically.
- [ ] Historical OHLCV, trend and volatility are joined without temporal leakage.
- [ ] Each strategy has a conditional-performance heatmap with counts, costs and uncertainty.
- [ ] At least one AI-generated hypothesis cites genuine tool output.
- [ ] A fixed rule and a model-derived strategy gate are simulated with execution costs.
- [ ] An untouched chronological test compares **always-on / always-off / simple-rule / meta-model**.
- [ ] “Agent + news” is compared with “market-only” where valid news coverage exists, without silently dropping unmatched periods.
- [ ] A structured decision report shows both successes and failure cases.
- [ ] A prospective 14-day **paper-only** champion/challenger plan can be frozen and recorded.
- [ ] No user funds, private keys, or brokerage order endpoints are involved.

### Unit/integration tests to prioritise

- Test replacing a feature timestamp with `t+1` causes the temporal validator to reject it.
- Test positions entered on bar `t` cannot use bar `t` closing price as a same-instant executable fill.
- Test switching on/off increases transaction costs relative to remaining flat when appropriate.
- Test sealed holdout predictions are produced by a frozen policy without training on its labels.
- Test missing sentiment data produces missingness flags, not future-filled values.
- Test extreme drawdown/risk-limit cases force a monitored/off recommendation even if the LLM argues otherwise.

## 14. Two-week forward test protocol

This is a **planned experiment** at hackathon submission, not a completed claim:

- Freeze base-strategy versions, supervisory policy, model weights, thresholds, data feeds, and transaction-cost assumptions at day 0.
- Run champion (always-on) and challenger (gated) simultaneously against the same price stream in **shadow/paper mode**.
- Log proposed positions, simulated fills, fees/slippage, forecasted regime, market context and rationale each decision interval.
- Capture realised out-of-sample net returns, switching frequency, max drawdown, and differences against precommitted ranges.
- If evidence is insufficient after 14 days, return **MONITOR / INCONCLUSIVE**, extend observation with approval, and **do not retroactively tune** the original experiment.
- Operational alerts can turn paper allocation off for data/feed integrity failures, but any model retuning creates a new challenger experiment.

## 15. Risk, oversight, and ethics

- **No live orders or monetary accounts.** Paper/shadow evaluation only in the hackathon.
- **Deterministic controls** over maximum exposure, number of strategies, missing data, publication cutoffs, and allowable model outputs.
- **Human approval** before any change in allocation recommendations is deployed to a prospective paper policy.
- **No causality claims** merely from SHAP, clustering, sentiment correlation or retrospective bull/bear labels.
- **Licensing and attribution:** verify dataset rights, attribute Alternative.me where its index is shown, and retain URLs/provenance for news.
- **Auditability:** store source versions, hashes, timestamps, test windows, policy configurations, tool outputs, prompts/model identifiers and measured results.
- **Security:** never execute arbitrary uploaded strategy code without sandboxing. MVP imports data/signals; executable strategy plugins are a later feature.

## 16. AgentVerse Finance-track alignment

Based on the provided event slide rubric:

| Category | Weight | Demonstration |
|---|---:|---|
| Traceable reasoning | 25% | Dated evidence, agent tool calls, dataset lineage, policy rationale |
| Testing on unseen data | 25% | Frozen chronological holdout, fair baselines, robustness and negative results |
| Relevance and impact | 20% | Real capital-allocation decision for systematic traders |
| Risk controls and human oversight | 15% | Paper-only, hard limits, approval gate, abstention |
| Ambition and technical quality | 15% | Regime-aware evaluation, sentiment-aware hypotheses and agent-assisted meta-policy |

**Judges' critical question:** “Does the agent add measurable value beyond a simple regime filter?”  
**Correct response:** run the same holdout with and without agents/news, disclose costs and failure cases, and accept a negative result if the added layer does not help.

## 17. Commercial roadmap (not required for demo)

- **Phase 1:** research dashboard for uploaded backtests, regime analytics, and supervised paper gating.
- **Phase 2:** integrations with existing trading-agent platforms and quant backtesting systems; automated strategy-health monitoring.
- **Phase 3:** portfolio-level capital allocation with robust out-of-sample evaluation, costs, and governance controls.
- **Possible pricing:** per strategy / per research run / team seat. Do not claim demand or willingness to pay before talking to potential users.

### Competition and positioning

- **Qlib:** quantitative modelling, research workflows, backtesting. We can use its infrastructure; we're not claiming to replace it.
- **RD-Agent:** automates research/factor/model development. We supervise **frozen strategies** and focus on conditional allocation, market context and independent evaluation.
- **vectorbt:** backtesting engine. It does not itself solve agent-assisted evidence investigation and supervisory governance.
- **Conventional dashboards:** show historical aggregate performance, not a research workflow that tests whether proposed regime gates are exploitable ex ante.

## 18. Demo script (~3–4 minutes)

1. **Hook (20s):** “This trading agent lost money overall. Should we kill it?”
2. **Import (20s):** Show immutable strategy, backtest, and data timestamp checks.
3. **Discover (45s):** Reveal regime heatmap: apparent strengths during certain trend/volatility conditions, weak performance elsewhere.
4. **Investigate (40s):** Show AI agent evidence: dated news, sentiment and statistical tool calls; it proposes a testable gate.
5. **Evaluate (75s):** Show always-on, fixed-rule, and model/agent gate on **untouched** historical data, with after-cost results, switching and uncertainty; include a case where an attractive hypothesis fails.
6. **Decide (25s):** Show KEEP / CONDITIONAL / REDUCE / KILL / INCONCLUSIVE with hard risk checks.
7. **Future experiment (15s):** Show frozen 14-day shadow paper-trading plan, explicitly not yet completed.

### Closing line

> **Strategies don't have to be universally good to be useful. Keep or Kill finds out when they deserve capital, and tests that conclusion before letting an agent act on it.**

---

## 19. Fast-start commands (illustrative)

```bash
# Python environment (choose/pin a compatible 3.11 interpreter)
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic pydantic-ai polars duckdb pyarrow \
  numpy scipy statsmodels scikit-learn lightgbm vectorbt arch pytest

# Optional modules: install only when needed
pip install transformers torch hmmlearn ruptures shap

# Research infrastructure (optional; integration work required)
# pip install pyqlib
# pip install rdagent  # heavier environment / Docker expectations

# Run API (after implementing apps.api.main)
uvicorn apps.api.main:app --reload

# Separate frontend workspace
# cd apps/web && npm install && npm run dev
```

**Dependency note:** verify compatible package versions on the machines used for the hackathon; the lines above are a conceptual install set, not a tested lockfile. RD-Agent/QLib support constraints and data adapters should be validated separately.

## 20. Unanswered design decisions to resolve immediately in the team

- Use **spot BTCUSDT** or **BTC perpetual futures**? They have different execution and cost models. For fastest reproducibility use spot; for funding/microstructure research choose futures.
- What cadence? **1-hour bars** for the MVP; don't mix daily sentiment with intraday timing without availability lag.
- Are external strategy signals available? If not, ship with two frozen, reproducible strategies and label them as demo fixtures.
- Can we source sufficiently rich historical news with reliable first-seen times? If not, make news explanation a qualitative supporting screen and keep historical quantitative gating market-only.
- Is a second strategy necessary? Only add multi-strategy combination once single-strategy gates are statistically and operationally valid.

**North-star implementation priority:** One statistically honest end-to-end demo is more compelling than twenty subagents creating attractive but invalid backtests.
