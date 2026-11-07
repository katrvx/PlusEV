# Keep or Kill

**Don't rewrite the strategy. Discover when to trust it.**

AgentVerse 2026 · Finance track (supported by Jane Street) · UCL · 7–8 November 2026 · repo: +EV

> Keep or Kill is an AI-powered research supervisor for trading strategies. It uses historical market regimes, sentiment and news to discover **when** an existing strategy has an edge, then independently tests whether activating or disabling it under those conditions actually improves risk-adjusted returns on unseen data.

Hackathon MVP. Paper-only. Not a claim of validated alpha.

---

## The problem

A backtest gives you a Sharpe ratio, not an answer to the questions that decide whether a strategy keeps its capital. Traders routinely confuse three situations:

1. **Unlucky:** a valid strategy in a plausible drawdown.
2. **Condition-dependent:** it works in identifiable market conditions and fails in others.
3. **Broken:** the edge is gone, the backtest was flawed, or costs ate it.

An aggregate return chart can't tell these apart, and building point-in-time regime gates by hand is slow and easy to overfit.

**User:** an independent systematic trader or small quant team running 2–10 strategies.
**Decision:** keep, activate only in some conditions, reduce, combine, monitor, kill, or *inconclusive*.

## How it works

1. **Import** an existing strategy's timestamped target positions. The strategy is **immutable**: we never change its signals.
2. **Reconstruct context** at every decision: trend, volatility, volume, funding, sentiment, news, all **point-in-time** (`data_max_available_at <= decision_time`).
3. **Diagnose** where it works and fails: regime heatmaps with counts, costs and uncertainty.
4. **Investigate** with AI agents that propose falsifiable hypotheses, call allowlisted tools, and cite **evidence IDs** from real tool output.
5. **Propose a supervisory gate** (allocation multiplier 0 / 0.5 / 1 on top of the unchanged signals), from an allowlisted family only.
6. **Challenge it** against always-on, cash, a simple rule and a LightGBM gate, with next-bar fills, fees, slippage and switching costs, on a **sealed chronological holdout** tested once.
7. **Decide:** KEEP / ACTIVATE CONDITIONALLY / REDUCE / COMBINE / MONITOR / KILL / **INCONCLUSIVE**, with hard risk checks a deterministic arbiter applies (not an LLM).
8. **Paper-test:** freeze champion vs challenger for a 14-day shadow run. Recorded as a plan, never presented as a completed result.

**Agents propose and explain; deterministic code computes every number and makes every decision.**

```text
existing strategy (immutable) ─► import / validate / hash
                                        │
                  market OHLCV ─────────┼───────── sentiment / news (as-of)
                                        ▼
                         point-in-time feature store
                         ┌──────────────┴──────────────┐
                    quant evaluator               research agents
                  (regimes, stats, sims)     (diagnose, propose, critique)
                         └──────────────┬──────────────┘
                                        ▼
                 gate candidates: always-on · rule · LightGBM · agent
                                        ▼
                  sealed-holdout champion / challenger, after costs
                                        ▼
                   decision report + human approval ─► 14-day paper plan
```

## Docs

| Doc | What |
|---|---|
| [`KEEP_OR_KILL_PROJECT_SPEC.md`](KEEP_OR_KILL_PROJECT_SPEC.md) | **Authoritative spec**: idea, maths, data rules, evaluation, agents, API, risk, demo script |
| [`KEEP_OR_KILL_AGENTS.md`](KEEP_OR_KILL_AGENTS.md) | Handoff brief for the three lanes, shared contracts, collaboration rules, definition of done |
| [`LANE_B.md`](LANE_B.md) | What Lane B built, its interface, guardrails, adversarial review, and what it needs from Lane A |
| [`LANE_C.md`](LANE_C.md) | Web workspace, shared route constants and types, and the teammate integration guide |
| [`docs/INTEGRATION_DECISIONS.md`](docs/INTEGRATION_DECISIONS.md) | Choices made while putting Lane A, current Lane B, and Lane C on one branch |
| [`archive/`](archive/) | Earlier +EV design notes, kept for reference only |

## Team and lanes

| Lane | Owns | Output interface | Status |
|---|---|---|---|
| **A · Quant / Data** | `A/` (target layout was `packages/ingestion`, `feature_store`, `strategies`, `quant`, `evaluation`) | `run_experiment(...) -> ExperimentResult`, including a deterministic verdict and a recorded 14-day plan | on this branch |
| **B · Agents / Context** (Kate) | `packages/research_agents`, `meta_policy`, news enrichment | `investigate(experiment_id) -> InvestigationReport` | current `main` agents (adversarially reviewed twice, 79 tests, first full Argon run on real data). Default loader is the synthetic stand-in. `--lane-a` uses Lane A's development view |
| **C · API / UI / Demo** | `apps/api`, `apps/web`, docs, practice-plan interface | consumes native Lane B reports; adapts Lane A results into UI contracts | on this branch. BTCUSDT 1h position imports are scored by A and B. Start at [`LANE_C.md`](LANE_C.md). |

Work on branches per lane; don't edit another lane's directories without coordinating. Freeze shared Pydantic contracts before integrating.

## Target layout

```text
apps/api            FastAPI routes                       (C)
apps/web            Next.js UI                           (C)
packages/contracts  Part C TypeScript types + API constants (C)
packages/contracts_lane_b  native Python research contracts (B)
packages/ingestion, feature_store, strategies, quant, evaluation   (A)
packages/research_agents, meta_policy                    (B)
packages/paper      paper-only shadow runner             (C)
data/fixtures       tiny reproducible sample
experiments/        run manifests, hashes, outputs
tests/              no-future-data, execution lag, switching costs, holdout isolation, baselines
```

Lane A’s code is in [`A/`](A/). The simple rule can allocate 0. A train-only regime filter can sit a strategy out where its own interval is entirely below zero. The arbiter returns KEEP, MODIFY, RESTRICT, MONITOR, KILL, or INCONCLUSIVE from the sealed test. COMBINE needs a second strategy, so a one-book run does not emit it. The 14-day paper plan records the policy that verdict chose, with `completed=false`. News is still omitted.

`python3 scripts/run_investigation.py --lane-a --fallback` runs Lane B's deterministic agents on Lane A's loader. That view keeps the test window's dates and drops its metrics, the verdict, and the paper plan. `--frozen` then scores the accepted champion once. `plusev/` and the Streamlit app are the earlier kit and do not call this path.

The repo root also holds the earlier prototype (`plusev/`, `app/`, `scripts/build.py`, `scripts/paired_challenge.py`, `eval/`): regime tagging, a kit-exact simulator and a governor tested in the organisers' challenge mode. That prototype is unchanged on this branch. See [`archive/`](archive/).

## Run (Lane B)

Python 3.10+ (on macOS: `uv venv --python 3.12 && source .venv/bin/activate`; LightGBM needs `brew install libomp`, otherwise it is skipped).

```bash
pip install -r requirements-lane-b.txt
python3 -m pytest -q tests/test_lane_b.py           # 79 guardrail + regression tests
python3 scripts/run_investigation.py --fallback      # deterministic agents -> experiments/investigation_fixture.json
KOK_AGENT_MODEL=google:gemini-3.8-flash GEMINI_API_KEY=... python3 scripts/run_investigation.py   # LLM agents
```

## How this maps to the judging rubric

| Criterion | Weight | Where |
|---|---:|---|
| Traceable reasoning | 25% | evidence IDs on every claim, tool-call log, dataset hashes, policy rationale |
| Testing on unseen data | 25% | sealed chronological holdout tested once, fair baselines, costs, uncertainty, negative results shown |
| Relevance and impact | 20% | a real capital-allocation decision for systematic traders |
| Risk controls and oversight | 15% | paper-only, hard limits, deterministic arbiter, human approval, INCONCLUSIVE allowed |
| Ambition and technical quality | 15% | regime-aware evaluation, agent-assisted meta-policy, LightGBM gate, news as point-in-time context |

Judges' key question: *does the agent add measurable value beyond a simple regime filter?* We answer it by running the same holdout with and without the agent layer and reporting the result either way.

## Data and licences

Binance Vision public data (CC BY-NC-SA 4.0, attribute "Binance Vision"); Alternative.me Fear & Greed (attribution required); news only with source URL, first-seen timestamp and content hash. No real accounts, keys, orders or personal financial data.

## Licence

MIT.
