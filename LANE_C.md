# Lane C — API, web workspace, and demo

## Teammate handoff: wire these current constants first

This is the concrete integration map for Lane A/B. It describes the code that exists in this checkout; it is not a new speculative contract.

Lane B is already merged into the current `main` checkout. Do not cherry-pick or merge a separate Lane B branch for this handoff; write its native report artifact and let the Part C reader discover it.

| Need | Current file / export | Value to use |
|---|---|---|
| Shared browser types | [`packages/contracts/index.ts`](packages/contracts/index.ts) | Re-exports `types.ts`, `research.ts`, and `api.ts` |
| Browser route constants | [`packages/contracts/api.ts`](packages/contracts/api.ts) | `API_PREFIX`, `DEFAULT_API_URL`, `CONTRACT_VERSION`, `API_ROUTES` |
| User strategy/experiment types | [`packages/contracts/types.ts`](packages/contracts/types.ts) | `Strategy`, `Experiment`, `PaperPlan`, `Health` (preserve Lane A’s native Python contracts) |
| Native Lane B report types for the UI | [`packages/contracts/research.ts`](packages/contracts/research.ts) | `AgentMode`, `TeamEvidence`, `TeamHypothesis`, `TeamReport`, `InvestigationWrapper`, `InvestigationSummary` |
| Main API client | [`apps/web/src/lib/api.ts`](apps/web/src/lib/api.ts) | `api.health()`, `strategies()`, `preview()`, `importStrategy()`, `experiments()`, `investigate()`, `freezePaperPlan()` |
| Native investigation client | [`apps/web/src/lib/team-api.ts`](apps/web/src/lib/team-api.ts) | `teamApi.investigations()` and `teamApi.investigation(experimentId)`; its type exports re-export `packages/contracts/research.ts` |
| API route registration | [`apps/api/main.py`](apps/api/main.py) | `app.include_router(team_reports_router)` is already present |
| Native Lane B reader | [`apps/api/team_reports.py`](apps/api/team_reports.py) | `router` has prefix `/api`; reads trusted investigation artifacts on each request |

### Five-minute wiring path

1. Put a real Lane B `InvestigationReport` at `experiments/investigation_<name>.json`. Reload `GET /api/investigations`; real artifacts take precedence over the bundled fixture.
2. The non-demo branch of `create_experiment()` in `apps/api/main.py` queues `apps/api/engine.py` for BTCUSDT 1h positions. That worker calls Lane A and `investigate(..., loader=...)`, writes `experiments/investigation_<id>.json`, and persists the presentation with `db_insert`. `run_demo_experiment()` stays restricted to seeded demos.
3. For an imported strategy, read the immutable paths already stored by `import_strategy()`: `data/local/uploads/<upload_id>_<filename>` (`raw_path`) and `data/local/canonical/<strategy_id>.json` (`canonical_data_path`). Use the stored `raw_data_hash`, `canonical_data_hash`, `dataset_hash`, `strategy_id`, and execution assumptions when creating the Lane A snapshot.
4. Return measured metrics and research findings only after Lane A and Lane B have run. Keep the browser as a formatter; it must not calculate returns, Sharpe, drawdown, or costs.
5. `GET /api/health` returns `{ "status": "ok", "research_engine": true, "version": "0.1.0-part-c" }` because the BTCUSDT hourly path above is the deterministic engine. Other imports are still refused.

The web proxy uses `API_URL` from [`apps/web/.env.example`](apps/web/.env.example), defaulting to `http://127.0.0.1:8000`. The API’s verified local constants are `ROOT = Path(__file__).resolve().parents[2]`, `DATA_DIR = ROOT / "data" / "local"`, `UPLOAD_DIR = DATA_DIR / "uploads"`, `DB_PATH = DATA_DIR / "keep_or_kill.sqlite3"`, `MAX_UPLOAD_BYTES = 10 * 1024 * 1024`, and `MAX_IMPORT_ROWS = 250_000`.

### Current status flags are deliberate

- Seeded demo strategies may use `mode: "demo"` and replay the checked-in illustrative fixture.
- Trade logs and imports other than BTCUSDT 1h stay `status: "awaiting_engine"`, `mode: "pending"`, with empty metrics and `verdict: "INCONCLUSIVE"`. A BTCUSDT hourly position file is scored and stored as `mode: "measured"`.
- A pending user upload must never receive demo metrics or agent findings. Do not flip it to `demo` to make the UI look complete.
- Native Lane B reports preserve `agent_mode: "llm" | "llm_with_fallback" | "deterministic_fallback"`; the UI labels fallback reports as scripted research and does not imply a live model call.

### Native Lane B boundary and sample

`apps/api/team_reports.py` loads `experiments/investigation_*.json` as `source: "team_artifact"`. If none exist, it loads the exact bundled [`apps/api/fixtures/lane_b_investigation.json`](apps/api/fixtures/lane_b_investigation.json) as `source: "bundled_lane_b_fixture"`, `synthetic: true`. The wrapper preserves the native `report` object, including `evidence_id`, `holdout_accessed`, `diagnostic.hypotheses`, `trial_log`, `candidates`, `test_requests`, and raw evidence payloads.

The native routes are:

```text
GET /api/investigations
GET /api/investigations/{experiment_id}
```

Example identifying fields from the bundled report (the complete payload is in the linked file):

```json
{
  "experiment_id": "exp_fixture_32a792b6",
  "agent_mode": "deterministic_fallback",
  "holdout_accessed": false,
  "n_policies_tried": 3
}
```

The completed demo response shape is also captured in [`docs/examples/experiment.demo.json`](docs/examples/experiment.demo.json) (explicitly illustrative; it is not a user-upload result).

The rest of this document explains the implementation and demo in more detail.

The Part C implementation lives on `lane-c`. It adds `apps/api` and `apps/web`; it does not replace the earlier Streamlit prototype or change Lane A/B strategy and research code.

## Run locally

Requirements: Node.js 22+ and Python 3.11+. Development was checked on Windows, Node 22, and Python 3.14.

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lane-c.txt
npm ci
```

Start the API in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Start the web app in a second terminal:

```powershell
npm run dev
```

Open <http://127.0.0.1:3000>. On macOS/Linux, substitute `.venv/bin/python` for the Windows Python path. The Next.js server proxies `/api/*` to the API; no separate browser CORS configuration is needed. `apps/web/.env.example` documents an optional `API_URL` override.

This is a local development service with no account authentication. Both servers bind to loopback by default. Before shared hosting, add authentication, per-user ownership checks, request/upload limits, durable job execution, and deployment configuration. No hosted service has been created by this change.

## What works

- Strategy library, CSV/Parquet import wizard, column mapping, raw preview, execution assumptions, validation, and immutable source/canonical hashes.
- Timestamped target positions (`decision_time`, `symbol`, `target_position`), where exposure is a capital fraction in `[-1, 1]`.
- Completed round-trip trade logs (`entry_time`, `exit_time`, `symbol`, `side`, `quantity`, `entry_price`, `exit_price`), explicitly marked **diagnosis only**.
- One strategy/instrument per import. Multiple source column names are supported through mapping; share/contract quantities are not silently converted into portfolio weights.
- Offset timestamps normalize to UTC. Naive timestamps use the explicit import timezone; ambiguous/nonexistent DST times are rejected.
- SQLite-backed saved strategies, jobs, and planned paper experiments. Raw and normalized files stay in gitignored `data/local`, outside the public web directory.
- Dashboard, condition heatmap, evidence drawers, research trace, policy comparison, JSON report export, and explicit approval for a frozen 14-day paper plan.
- Native Lane B investigation viewer with hypotheses, full trial logs (including refusals), candidate reasons, limitations, model/fallback provenance, and raw evidence.
- Loading, service failure, incomplete research, insufficient evidence, and missing evaluator states.

Imports accept UTF-8 CSV or Parquet, up to 10 MB and 250,000 rows. CSV headers must be unique. Typical Python/pandas/Polars exports work with mapping. Native TradingView paired entry/exit exports and QuantConnect orders are **not** advertised as automatically supported round-trip adapters. Export canonical target positions, or convert fills into completed trades first.

## What the demo means

The dashboard ships with two **illustrative UI fixtures**, explicitly labelled in the interface. Their curves and research steps are examples, not backtests of market data. A replay loads stored fixture output; it does not invoke an LLM. Imported user data never receives those metrics or findings.

The separate **Agent research** page reads authentic Lane B report artifacts. If no local `experiments/investigation_*.json` files exist, it reads the bundled exact `origin/lane-b` fixture at `apps/api/fixtures/lane_b_investigation.json`. That artifact uses Lane B's deterministic fallback and synthetic Lane A stand-in. Both are displayed explicitly. A candidate accepted for a frozen test is not described as having passed that test.

A paper plan is a saved future protocol with policy, execution assumptions, dataset hash, and evaluation windows. This change does **not** implement a paper runner or collect 14 days of returns.

## Connect the team lanes

### Lane B (already connected at the artifact boundary)

Write native `InvestigationReport` JSON to `experiments/investigation_<name>.json`. Part C reads these files when `/api/investigations` is requested, so reload the Agent research view after generating a report. Native artifacts take precedence over the bundled fallback.

The viewer preserves `evidence_id` and displays `agent_mode`, `model_id`, `holdout_accessed`, `diagnostic.hypotheses`, `trial_log`, `candidates`, `test_requests`, `limitations`, and raw tool evidence. It does not rename Lane B's Pydantic contracts or require merging the rest of that branch.

### Lane A and live research execution

`POST /api/experiments` scores a BTCUSDT hourly position import in the background: Lane A aligns the targets to the Binance spot snapshot, then Lane B's `investigate(..., loader=...)` reads the development view. The investigation JSON is written under `experiments/`. Trade logs and other markets stay `awaiting_engine` and never receive demo metrics. `research_engine` on `GET /api/health` is true for this path.

For imported inputs, the strategy record retains `canonical_data_path`, `canonical_data_hash`, `raw_path`, `raw_data_hash`, `source_mapping`, and execution assumptions. Use those immutable inputs to construct Lane A's dataset snapshot. Canonical position rows contain decision time, symbol, and target position; attach strategy ID/version from the parent record.

`packages/contracts/types.ts` is the **Part C presentation model**, not a replacement for Lane B's `packages/contracts_lane_b` or `research_agents/models.py`. Adapt completed quantitative output into `Experiment` only after the relevant stage exists. Derive all financial metrics in Lane A; the browser only formats received values. Keep an imported experiment pending/inconclusive when holdout evaluation is missing. Do not convert research-stage candidate acceptance into a holdout pass.

See `docs/PART_C_CONTRACT.md` and the generated API docs at <http://127.0.0.1:8000/docs> for routes and shapes.

## Checks

```powershell
npm run typecheck
npm run build
.\.venv\Scripts\python.exe -m pytest tests/api -q
```

The API tests use temporary storage so they do not add test strategies or plans to the user's workspace. The legacy prototype suite is separate and requires its own dependencies and organiser datasets.

## Short demo walkthrough

1. Open the BTC Trend Following UI fixture and point out its illustrative badge.
2. Inspect a market-condition cell and the linked evidence; compare policies and inspect the decision.
3. Open **Agent research** to inspect the actual Lane B fallback report, its trial log, and future test candidates.
4. Import `docs/examples/positions.csv`; inspect the mapping, fee/slippage assumptions, and saved source hash.
5. Start an investigation on the imported strategy and show the explicit awaiting-engine state.
6. For a fixture, review the future paper plan, check the approval box, and record it. Show that its status is planned, not running.


## UI direction

The interface targets traders who understand basic strategies but are not quantitative researchers. The overview leads with where a strategy worked, where it struggled, and the next useful test. Plain-language labels come first; evidence, uncertainty ranges, execution assumptions, and technical identifiers open on demand. The How it works page explains the workflow and provides concrete position/trade examples. Imports use a three-step upload, match, and review flow with sample CSVs and inline validation.

The visual system uses locally bundled Inter, a quiet light research area, dark navigation, and a purple action color. Responsive layouts preserve readable type and touch targets. Illustrative UI examples and the authentic scripted agent report remain explicitly distinguished from measured results.

Native reports preserve mixed-model fallback status and all current Lane B fields. The checked-in `experiments/investigation_fixture.json` is explicitly labelled sample market data even though its source is `team_artifact`. Other filenames are not assumed to prove measured market data; the source badge describes the artifact, not profitability. Baseline candidates with `status: "competitor"` appear as comparisons, not rejections.
