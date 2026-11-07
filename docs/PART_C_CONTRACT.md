# Part C integration contract v1

## Teammate handoff — exact integration points

Use these current files and exports when wiring the lanes; no new adapter names are needed:

Lane B is already present in the current `main` checkout. There is no separate Lane B merge step: the integration boundary is the native JSON artifact under `experiments/investigation_<name>.json`, which Part C discovers on each request.

- Shared TypeScript barrel: [`packages/contracts/index.ts`](../packages/contracts/index.ts), which exports [`types.ts`](../packages/contracts/types.ts), [`research.ts`](../packages/contracts/research.ts), and [`api.ts`](../packages/contracts/api.ts).
- Route constants: `API_PREFIX`, `DEFAULT_API_URL`, `CONTRACT_VERSION`, and `API_ROUTES` in [`packages/contracts/api.ts`](../packages/contracts/api.ts).
- UI clients: `api` in [`apps/web/src/lib/api.ts`](../apps/web/src/lib/api.ts) and `teamApi` in [`apps/web/src/lib/team-api.ts`](../apps/web/src/lib/team-api.ts).
- API implementation: [`apps/api/main.py`](../apps/api/main.py); native Lane B router: [`apps/api/team_reports.py`](../apps/api/team_reports.py).
- Native Lane B sample: [`apps/api/fixtures/lane_b_investigation.json`](../apps/api/fixtures/lane_b_investigation.json).

For a quick connection, write a real Lane B report to `experiments/investigation_<name>.json`, then call `GET /api/investigations`. For Lane A, wire the **non-demo branch of `create_experiment()`** in `apps/api/main.py` to a background worker calling the evaluator and Lane B `investigate(..., loader=...)`. Persist progress/results with `db_insert("experiments", experiment_id, payload)`. `run_demo_experiment()` is a job-state example, and must stay restricted to seeded demos. Imported user data stays pending until the real worker supplies measured output.

The current proxy key is `API_URL` in [`apps/web/.env.example`](../apps/web/.env.example), defaulting to `http://127.0.0.1:8000`. Current API storage constants are `ROOT = Path(__file__).resolve().parents[2]`, `DATA_DIR = ROOT / "data" / "local"`, `UPLOAD_DIR = DATA_DIR / "uploads"`, `DB_PATH = DATA_DIR / "keep_or_kill.sqlite3"`, `MAX_UPLOAD_BYTES = 10 * 1024 * 1024`, and `MAX_IMPORT_ROWS = 250_000`.

The accepted UI modes are intentionally limited: `demo` for seeded illustrative fixtures, `pending` for imported strategies awaiting the evaluator, and `measured` only for evaluator-produced results. Do not attach dummy user results to a pending upload. The health flag remains `research_engine: false` until the deterministic engine is wired.

For a concrete completed demo response, see [`docs/examples/experiment.demo.json`](examples/experiment.demo.json). It is an explicit fixture export and must not be reused for imported user data.

UI types: `packages/contracts/types.ts`. The API validates and persists imported strategy data. Parts A and B supply real evaluation and research. All fixture outputs must be marked `mode: demo` and described as illustrative; imported strategies never inherit fixture metrics. No real brokerage execution or arbitrary uploaded code.

## Routes

- GET /api/health -> Health
- GET /api/strategies -> Strategy[]
- POST /api/imports/preview (multipart file) -> ImportPreview
- POST /api/strategies/import (ImportRequest JSON) -> ImportResult; validation failures return valid=false and issues with no strategy persisted
- GET /api/templates/positions.csv -> downloadable canonical target-position example
- GET /api/templates/trades.csv -> downloadable generic trade-log example
- GET /api/experiments?strategy_id=... -> Experiment[] (newest first)
- POST /api/experiments {strategy_id} -> Experiment, async job; demo fixtures replay stored research, user uploads return awaiting_engine until Parts A/B are connected
- GET /api/experiments/{id} -> Experiment
- GET /api/experiments/{id}/report -> downloadable Experiment JSON
- POST /api/paper-tests {experiment_id, duration_days:14, approved:true} -> PaperPlan; persist immutable planned record, no trading started
- GET /api/paper-tests -> PaperPlan[]
- GET /api/investigations -> native Lane B artifact summaries with agent/data provenance
- GET /api/investigations/{experiment_id} -> {source, synthetic, source_path, report}; report preserves the native InvestigationReport schema and evidence IDs

CSV and Parquet are file inputs. Canonical positions: decision_time, symbol, target_position (fraction of capital, -1..1). Strategy ID/version may come from import metadata. Canonical trades: entry_time, exit_time, symbol, side, quantity, entry_price, exit_price; diagnostic only. Column mapping supports exports with different names; do not claim arbitrary TradingView paired-row exports or QuantConnect orders are normalized into round trips. Timestamps with offsets normalize to UTC; naive timestamps require explicit supplied timezone, DST ambiguities rejected. Reject missing fields, nonfinite numbers, future dates, invalid target positions, duplicate symbol/timestamp positions. Preserve a content hash and row counts, surface nonmonotonic source timestamps if sorting is applied. CSV preview has bounded rows and max upload size.

Store uploaded data outside public web directories under gitignored data/local. Limit each input to 10 MB and 250,000 rows. Imported experiments use mode=pending while awaiting the research engine; demo means illustrative, measured means evaluator-produced. User-facing UI has loading/error/empty/missing-evidence states. Imported backtests are user-supplied historical data, not independently validated performance. Experiment metrics are API outputs; UI does not calculate returns/Sharpe/drawdown. Part C types are presentation models; preserve native Lane A/B contracts and use an adapter at the orchestration boundary.

Native reports preserve mixed-model fallback status and all current Lane B fields. The checked-in `experiments/investigation_fixture.json` is explicitly labelled sample market data even though its source is `team_artifact`. Other filenames are not assumed to prove measured market data; the source badge describes the artifact, not profitability. Baseline candidates with `status: "competitor"` appear as comparisons, not rejections.
