# Keep or Kill — Coding Agent Instructions

This file is the handoff brief for three developers with coding assistant subscriptions and parallel subagents. Read `KEEP_OR_KILL_PROJECT_SPEC.md` first. The business idea, evaluation contract and safety constraints there are authoritative.

## Product invariant

The system **never rewrites the underlying trading strategy**. It reconstructs historical conditions and develops a **supervisory allocation gate** applied to the immutable strategy signals. It must evaluate all gates on chronologically unseen data, account for switching costs, and allow inconclusive outcomes. Paper-only, no real trades.

## Shared contracts to agree first

- All timestamps in UTC, documented decision cutoff and bar convention.
- A signal is `{strategy_id, symbol, decision_time, target_position, strategy_version}`.
- A context row is `{decision_time, symbol, point_in_time_features, data_max_available_at}`.
- A policy output is `{strategy_id, decision_time, allocation_multiplier, policy_id, rationale_evidence_ids}`.
- Return a stable `experiment_id`, dataset hashes, model/policy version, and explicit train/validation/test windows.
- Every metric is calculated by deterministic code, never invented by an LLM.

## Lane A — Quant / Data

**Files owned:** `packages/ingestion`, `feature_store`, `strategies`, `quant`, `evaluation`, time-leakage tests.

**Build in order:** (1) Binance OHLCV importer and deterministic frozen sample strategy positions; (2) as-of join and missingness stats; (3) next-bar fill simulator, fees and turnover; (4) 3 regimes using lagged trend/vol; (5) always-on/cash/rule-gate benchmark; (6) chronological train/validation/holdout evaluation; (7) LightGBM gate evaluation.

**Required tests:** explicit next-bar fill; no future-available context; altered policy causes extra fees; untouched holdout isolation; missing-data coverage report.

**Output interface:** `run_experiment(strategy_id, dataset_snapshot_id, policy_spec) -> ExperimentResult` containing timeseries, per-regime returns, baselines, uncertainty and audit IDs.

## Lane B — Agent / Context

**Files owned:** `packages/research_agents`, `meta_policy`, news enrichment (coordinate feature schema with A).

**Build in order:** (1) Pydantic output models; (2) four allowlisted tools: `regime_performance`, `cost_attribution`, `news_context`, `test_gate_train`; (3) diagnostic agent; (4) critic agent; (5) gate proposer using whitelist of parameters; (6) optional semantic news labelling with first-seen timestamps.

**Required guardrails:** no arbitrary uploaded code execution; no changes to strategy code; no unrestricted historical news backfill claims; no access to held-out labels while developing policy; all claims link to evidence IDs.

**Output interface:** `investigate(experiment_id) -> InvestigationReport` with ranked hypotheses, evidence, test requests, accepted/rejected policy candidates, and limitations.

## Lane C — API / UI / Demo

**Files owned:** `apps/api`, `apps/web`, docs, paper-run interface.

**Build in order:** (1) frozen fixture import and `/api/strategies`; (2) `/api/experiments` job + status; (3) strategy equity curve and heatmap; (4) evidence timeline; (5) champion/challenger charts and metric table; (6) decision report + frozen 14-day paper plan; (7) scripted demo.

**Required UI states:** loading, error, data gaps, ‘not enough evidence,’ out-of-sample validation missing. Always show whether numbers are simulated/illustrative or measured.

**Output interface:** UI consumes `ExperimentResult` and `InvestigationReport`; never recalculates financial metrics in JavaScript.

## Collaboration rules

1. Freeze Pydantic schemas and shared sample fixtures **before** parallel implementation.
2. Work in separate git branches/worktrees. Do not modify another lane's code without coordination.
3. Use independent subagents to **audit** temporal assumptions, statistical validity and UI/API contracts, not just generate more features.
4. Integrate a working vertical slice early: CSV → feature join → rule gate → compare → report.
5. Don't open the sealed holdout to brainstorm gates. Once a candidate is tested there, any changes create a *new* research experiment with a new untouched period.
6. If time is running out, cut HMM, RD-Agent and news analysis before cutting execution correctness or benchmarks.

## Definition of done

- Two immutable demo strategies, imported or generated reproducibly.
- Conditional performance dashboard with counts and uncertainty.
- Base strategy, rule gate, meta-model gate compared after costs on frozen unseen data.
- Agent investigations use genuine tool output/evidence IDs.
- Risk constraints and human approval gate demonstrated.
- Paper-only 14-day champion/challenger plan recorded, not misrepresented as completed.
- `pytest` contains adversarial timing/cost tests and passes.

## Product pitch

> Keep or Kill is the intelligence layer for existing trading strategies: it finds where each strategy works using historical market context and sentiment, tests an activation/allocation overlay without rewriting the strategy, and makes a transparent keep, reduce, combine or kill recommendation backed by unseen-data evidence.
