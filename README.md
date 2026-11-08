# +EV

**Don't rewrite the strategy. Discover when to trust it.**

AgentVerse 2026 · Finance track (supported by Jane Street) · UCL · 7–8 November 2026 · repo: +EV

>+EV is an AI-powered research supervisor for trading strategies. It uses historical market regimes and sentiment to discover **when** an existing strategy has an edge, then independently tests whether activating or disabling it under those conditions actually improves risk-adjusted returns on unseen data. News is omitted: there is no first-seen archive.



## For judges: a 2-minute tour

**What it does.** You give it an existing trading strategy, and it never changes the strategy's signals. AI agents work out when the strategy has an edge: which trend, volatility, liquidity and sentiment regimes it makes money in. They propose a simple on/off rule (a "gate"). Deterministic code then decides, by a rule fixed in advance, whether that gate deserves a single test on data held back from the research.

**Real result on real data.** Binance spot BTCUSDT hourly bars, 2018-02-01 to 2026-10-31, with Fear & Greed. Research period 2018-02 → 2023-05, validation 2023-05 → 2025-02, test 2025-02 → 2026-10, scored once. The two demo strategies and their costs (10 bp + 1 bp) were fixed before the run. Agents ran on Gemini 4 Argon. Differences between a gate and the strategy as-is are in percentage points (pp):

| | Trend (`btc-trend-24-72-demo`) | Mean reversion (`btc-meanrev-48-demo`) |
|---|---|---|
| Strategy as-is | Research +276%; validation +134% (90% CI +14% … +413%) | Research −90%; validation −19% |
| Unlucky or broken? | 43 of 45 two-week validation blocks inside the research range, 2 above it | 45 of 45 inside the research range. That range comes from a period in which it lost 90% |
| Agent gates | 3 proposed, **all vetoed by the critic**. The best, "trade only when Fear & Greed > 28", beat as-is by 32 pp on validation. But sentiment had flipped (fear fell from 51% to 10% of the time), so the gate was on 97% of the time, and on the first research fold it trailed as-is by 48 pp | Champion: half size when 7-day volatility is below its research median. Validation +26.8 pp vs as-is (CI above zero), +7.3 pp vs cash, 3/3 research folds, critic approved. Holding a constant half size alone gives +11.1 pp |
| Test (one look) | Lane A arbiter: **INCONCLUSIVE** (intervals contain zero) | Gate vs as-is +27.3 pp (90% CI +15.3 … +36.2), drawdown 60% → 36%, but **net −28.9%: it still loses money**. Its average size was 0.55× as-is, so much of the gain is holding less of a losing strategy. Lane A arbiter:

| Kit challenge, 300 paths | Mean reversion | Trend |
|---|---|---|
| Gate on vs gate off, same paths | Gate better on 53, worse on 12, identical on 235 (sign test p = 3×10⁻⁷). Mean +0.93% of capital (90% CI +0.58 … +1.29), drawdown 1.1 pp smaller | Better 2, worse 8, identical 290 (p = 0.11): **untestable**. The 12–80-bar paths are shorter than its 72-bar warm-up, so it is flat on ~95% of them |
| Is that skill? | **No.** Cash beats the gated strategy on 56 paths vs 8 (p = 6×10⁻¹⁰). In the kit's all-in execution, half size rounds to flat, so the gate helps only by being out of the market more (exposure 0.50× of raw) | Cash beats it 10 vs 4 (p = 0.18) |
| Kit verdict vs buy-and-hold | 189 wins vs 111 (p = 8×10⁻⁶), but it beats cash on only 8 paths: it wins mostly by sitting in cash on falling paths. Without the gate: 185 vs 115 | 198 vs 102, same reason: almost always flat |

Same conclusion as on real data: the gate reliably loses less by holding less. It does not make the strategy worth running. A kit "beat buy-and-hold" verdict here comes from staying in cash, which is why we report the comparison with cash next to it.

Reproduce: `python3 scripts/kok_challenge.py challenge --strategy mean_reversion` runs the kit's `challenge` with the gated adapter, then `python3 scripts/kok_challenge.py replay --strategy mean_reversion --seed <revealed seed>` runs the same cases without the gate. To plug our agent into the kit directly, the adapter is `python3 -m packages.kit_adapter.kok --strategy {mean_reversion,trend} --mode {gated,raw}`.

**Show one control live (offline, about 4 seconds):** `python3 scripts/demo_controls.py` runs 4 controls: the sealed test split is refused to an agent; an invented number is rejected and the agent retries with copied numbers; a money-losing gate the AI critic approved is rejected by code; and a second look at the test split is refused even under a new name. `--only 2` runs one. It exits 1 if any control fails.

The agents propose and explain; **code computes every number and makes every decision.**

**Where to look**

| What | Where |
|---|---|
| The two agent reports (every claim cites an evidence id from a real tool call) and the one sealed look | `experiments/investigation_argon_lane_a.json`, `experiments/investigation_argon_meanrev.json`, `experiments/frozen_look_btc-meanrev-48-demo.json`, or the web app → Explore → Evidence → *Open agent report* |
| How the agents are kept honest | [`LANE_B.md`](LANE_B.md): number verifier, sealed holdout, pre-registered rule, four adversarial reviews |
| Data, costs, baselines, arbiter, 14-day paper plan | [`A/README.md`](A/README.md) |
| Web app and API | [`LANE_C.md`](LANE_C.md) |
| Where we deliberately cut scope | [`docs/LANE_B_DIVERGENCE.md`](docs/LANE_B_DIVERGENCE.md), and the `limitations` list in each report |

**Run it** (Python 3.11+, Node 22+; on macOS `brew install libomp` for LightGBM):

```bash
pip install -r requirements-lane-b.txt -r requirements-lane-c.txt && npm ci
python3 -m pytest -q tests/ A/tests                              # 255 tests: leakage, costs, holdout, verifier, kit adapter, API
python3 -m uvicorn apps.api.main:app --port 8000 &                # API
npm run dev                                                        # web app on http://127.0.0.1:3000
python3 scripts/run_investigation.py --lane-a --fallback          # agents without an API key (deterministic)
KOK_AGENT_MODEL=google:gemini-4-argon GEMINI_API_KEY=... python3 scripts/run_investigation.py --lane-a   # LLM agents
python3 scripts/frozen_look.py --report experiments/<committed report>.json   # the one sealed look, refused if already taken
python3 scripts/demo_controls.py                                  # 4 risk controls, live, offline
```

**Honest limits.** Two demo strategies on one market (BTC), not imported live strategies, and not claimed as alpha. No news archive with first-seen timestamps exists for us, so news is not used and every run is market-only (the point-in-time news store is built and tested). The 14-day paper plan is an approved hourly shadow log; the stored book ends at 2026-10-31 23:00 UTC, so the log has no bars yet and is not a result. Nothing here trades real money.

---

## The problem

A backtest gives you a Sharpe ratio, not an answer to the questions that decide whether a strategy keeps its capital. Traders routinely confuse three situations:

1. **Unlucky:** a valid strategy in a plausible drawdown.
2. **Condition-dependent:** it works in identifiable market conditions and fails in others.
3. **Broken:** the edge is gone, the backtest was flawed, or costs ate it.

An aggregate return chart can't tell these apart, and building point-in-time regime gates by hand is slow and easy to overfit.

**User:** an independent systematic trader or small quant team running 2–10 strategies.
**Decision:** keep, activate conditionally, reduce, combine, monitor, kill, or not proven.

## How it works

1. **Import** an existing strategy's timestamped target positions. The strategy is **immutable**: we never change its signals.
2. **Reconstruct context** at every decision: trend, volatility, volume, and Fear & Greed, all **point-in-time** (`data_max_available_at <= decision_time`). News is omitted. There is no first-seen archive, coverage is 0, and a news feature cannot be a gate.
3. **Diagnose** where it works and fails: regime heatmaps with counts, costs and uncertainty.
4. **Investigate** with AI agents that propose falsifiable hypotheses, call allowlisted tools, and cite **evidence IDs** from real tool output.
5. **Propose a supervisory gate** (allocation multiplier 0 / 0.5 / 1 on top of the unchanged signals), from an allowlisted family only.
6. **Challenge it** against always-on, cash, a simple rule and a LightGBM gate, with next-bar fills, fees, slippage and switching costs, on a **sealed chronological holdout** tested once.
7. **Decide:** keep, activate conditionally, reduce, combine, monitor, kill, or not proven. The stored names are `KEEP`, `MODIFY`, `RESTRICT`, `COMBINE`, `MONITOR`, `KILL`, and `INCONCLUSIVE`. A deterministic arbiter applies the risk checks, not an LLM.
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
| [`A/README.md`](A/README.md) | Lane A: hourly book, costs, baselines, arbiter, paper plan, and the sealed verdicts |
| [`LANE_B.md`](LANE_B.md) | What Lane B built, its interface, guardrails, adversarial review, and what it needs from Lane A |
| [`LANE_C.md`](LANE_C.md) | Web workspace, shared route constants and types, and the teammate integration guide |
| [`docs/INTEGRATION_DECISIONS.md`](docs/INTEGRATION_DECISIONS.md) | Choices made while putting Lane A, current Lane B, and Lane C on one branch |
| [`docs/LANE_B_DIVERGENCE.md`](docs/LANE_B_DIVERGENCE.md) | Where Lane B still matches the original idea, and where the champion rule has moved |
| [`archive/`](archive/) | Earlier +EV design notes, kept for reference only |

## Team and lanes

| Lane | Owns | Output interface | Status |
|---|---|---|---|
| **A · Quant / Data** | [`A/README.md`](A/README.md) | `run_experiment(...) -> ExperimentResult`, including a deterministic verdict and a recorded 14-day plan | on this branch |
| **B · Agents / Context** (Kate) | `packages/research_agents`, `meta_policy`, news enrichment | `investigate(experiment_id) -> InvestigationReport` | current `main` agents (four agents, adversarially reviewed four times, 140 tests, walk-forward folds, bad-luck-vs-broken check, Argon run on real data). Default loader is the synthetic stand-in. `--lane-a` uses Lane A's development view |
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

Lane A’s code and results are in [`A/README.md`](A/README.md). The simple rule can allocate 0. A train-only regime filter can sit a strategy out where its own interval is entirely below zero. The screen says keep, activate conditionally, reduce, monitor, kill, or not proven. Those are the stored verdicts `KEEP`, `MODIFY`, `RESTRICT`, `MONITOR`, `KILL`, and `INCONCLUSIVE`. `COMBINE` needs a second strategy, so a one-book run does not emit it. LightGBM is fit on early train and calibrated on the last 25% of train, so validation stays untouched. The 14-day paper plan records the policy that verdict chose, with `completed=false`. News is still omitted.

`python3 scripts/run_investigation.py --lane-a --fallback` runs Lane B's deterministic agents on Lane A's loader. That view keeps the test window's dates and drops its metrics, the verdict, and the paper plan. `--frozen` then scores the accepted champion once. `plusev/` and the Streamlit app are the earlier kit and do not call this path.

The repo root also holds the earlier prototype (`plusev/`, `app/`, `scripts/build.py`, `scripts/paired_challenge.py`, `eval/`): regime tagging, a kit-exact simulator and a governor tested in the organisers' challenge mode. That prototype is unchanged on this branch. See [`archive/`](archive/).

## Run (Lane B)

Python 3.10+ (on macOS: `uv venv --python 3.12 && source .venv/bin/activate`; LightGBM needs `brew install libomp`, otherwise it is skipped).

```bash
pip install -r requirements-lane-b.txt
python3 -m pytest -q tests/test_lane_b.py           # 111 guardrail + regression tests
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
