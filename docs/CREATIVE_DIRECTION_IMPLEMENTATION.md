# Creative direction implementation map

This document is the integration guardrail for the redesign described in `KEEP_OR_KILL_CREATIVE_DIRECTION_PROMPT.md`. The redesign changes the presentation layer only. Existing import, storage, evaluation, report, evidence, and paper-plan interfaces remain the source of truth.

## Latest surface direction (user steering)

The final landing surface is intentionally sparse and reference-led: a quiet import invitation, a real example playback, and a short three-step orientation. This latest direction supersedes the earlier “no graph on the landing surface” interpretation of the brief. The landing graph is not a dashboard or a fabricated performance teaser: `apps/web/src/components/redesign/strategy-entry.tsx` replays only the seeded demo experiment's recorded `equity` points, labels the result as illustrative, and provides pause/replay plus reduced-motion behavior. File selection, drag-and-drop, “Try an example,” and “Your workspace” remain the entry actions.

The surface change does not change the product contract. Core import, strategy, experiment, native agent-report, report-download, and paper-plan APIs remain unchanged; the dense research workspace appears after the user leaves the entry surface. The landing playback must never be reused for imported strategies or presented as measured market performance.

## What must continue to work

| Existing capability | Source of truth | Redesign requirement |
|---|---|---|
| Preview a CSV/Parquet upload | `api.preview(file)` in `apps/web/src/lib/api.ts` → `POST /api/imports/preview` | Keep the native file chooser and the upload ID. Do not treat a filename as a run. |
| Map and save a strategy | `api.importStrategy(request)` → `POST /api/strategies/import` | Preserve `positions` versus `trades`, column mapping, timezone, fee bps, slippage bps, version, source mapping, validation issues, and `onImported`. |
| Load saved strategies | `api.strategies()` → `GET /api/strategies` | Preserve `strategy_id` as the selection identity. Do not use display names as keys. |
| Load an experiment | `api.experiments(strategyId)` / `api.experiment(id)` | Preserve `experiment_id`, stale-request guards, and the distinction between `queued`, `running`, `completed`, `awaiting_engine`, and `failed`. |
| Start research | `api.investigate(strategyId)` → `POST /api/experiments` | Demo strategies may replay the checked-in fixture. Imported strategies currently return `mode: "pending"` and no fabricated metrics. The UI must explain that the evaluator is not connected. |
| Native agent reports | `teamApi.investigations()` / `teamApi.investigation(id)` | Keep `source`, `synthetic`, `source_path`, `agent_mode`, `holdout_accessed`, evidence IDs, trial logs, candidate statuses, and raw evidence. Do not merge native Lane B reports into the `Experiment` shape. |
| Export a report | `API_ROUTES.experimentReport(experimentId)` | Keep the actual experiment identifier in the download URL. |
| Save a paper plan | `api.freezePaperPlan(experimentId)` → `POST /api/paper-tests` | This records a plan only. It does not start a runner, generate observations, or create a live order. Require the existing human approval state and server response. |
| Load plans | `api.paperPlans()` → `GET /api/paper-tests` | Render plans as planned/not started unless a future backend adds an observation contract. |

The shared route constants live in [`packages/contracts/api.ts`](../packages/contracts/api.ts). Presentation types live in [`packages/contracts/types.ts`](../packages/contracts/types.ts), and native Lane B report types live in [`packages/contracts/research.ts`](../packages/contracts/research.ts). The Next proxy uses `API_URL` from `apps/web/.env.example` and defaults to loopback port 8000.

## Current data boundaries

The current `Experiment` contract provides an equity series (`equity`) and aggregate regime records (`regimes`). Regimes have trend, volatility, net return, trade count, confidence interval, and an evidence ID, but they do not provide a timestamped trend/volatility series. The Conditions screen must therefore present aggregate historical conditions and their supplied intervals; it must not draw a time-aligned context track or invent condition values between observations.

`Experiment.metrics`, `baselines`, `equity`, `windows`, and `policy` are API values. The browser may format them but must not recalculate return, Sharpe, drawdown, fees, switching costs, confidence, or an unseen-test verdict. A demo equity series is illustrative. Imported strategies stay empty/pending until the evaluator supplies measured output.

Native Lane B reports are a separate artifact surface. The bundled or checked-in report may be sample market data and may use deterministic fallback. `agent_mode` can be `llm`, `llm_with_fallback`, or `deterministic_fallback`; candidate status can be `accepted_for_frozen_test`, `rejected`, or `competitor`. A competitor is a comparison rule, not a rejected agent finding. A report with `holdout_accessed: true` must visibly warn that the new-data test may no longer be unbiased.

## Features the backend does not currently provide

These are design constraints, not missing UI polish:

- There is no market-context time series in the Part C `Experiment` response.
- There is no paper-run observation endpoint, scheduled feed, stale-feed timestamp, day-by-day result, or decision-log endpoint.
- There is no cancellation endpoint for an experiment. Do not show a successful “cancelled” state or a cancel action that claims the server stopped.
- `Health.research_engine` is currently `false` in the local API. Uploaded strategies must remain `awaiting_engine` / `pending` with no metrics or agent findings.
- The existing backend does not expose a configurable starting balance, venue selector, date-range edit endpoint, or a rerun/version endpoint. Do not add controls that imply these settings are persisted when they are not.
- A paper plan is saved only after `approved: true` and the API response. The plan is not a running paper test and must not be rendered as measured performance.

### Retry-safe creation (small API hardening, no evaluator change)

`POST /api/experiments` and `POST /api/paper-tests` currently create a fresh ID for every request. A double click, browser retry, or network retry can therefore create duplicate records. The smallest backwards-compatible fix is an optional `Idempotency-Key` header on each route; requests without the header retain today's behaviour.

When the header is present, persist a key record in the same SQLite transaction as the business row. Scope it by route and store a canonical request hash (for example, the route plus sorted JSON from Pydantic `model_dump(mode="json")`). A repeated route/key with the same hash returns the original JSON response and does not enqueue a second demo replay; a reused key with a different hash returns `409`. The SQLite primary key should be `(route, key)`, and the check/insert should run under `BEGIN IMMEDIATE` (the existing process lock is useful but is not sufficient across API processes). Keep the stored response/status so a retry is byte-for-byte equivalent from the caller's perspective.

The web client can opt in later by generating one stable key per user action and reusing it for that action's retries. It must not generate a new key for every retry. No evaluator, runner, paper-observation, or existing request schema needs to change. Add focused tests for same-key replay, changed-payload `409`, and the legacy no-header path on both routes.

The creative brief's stages and motion IDs should describe actual state changes. A loading animation may accompany a real request; it must not simulate market progress, count to an invented percentage, reveal a profitable curve, or imply an agent is thinking when no request is active.

## Screen acceptance checklist

### Strategy / entry and import

- Use “Test your strategy” / “Add your strategy” language. Do not ask for a completed backtest or executable Python.
- Keep `ImportWizard`'s focus trap, native chooser, preview request, mapping selectors, validation issue display, upload lock, stale preview invalidation, and success callback.
- Preserve the entry context when the import dialog is cancelled: cancelling from the sparse landing returns to that landing; importing from the workspace returns to the workspace.
- Position history remains the recommended input for alternative-rule testing. Trade history remains diagnosis-only.
- Keep fee, slippage, timezone, strategy version, and source filename visible or available in an explicit disclosure. Do not silently change defaults.

### Explore / overview

- Show actual strategy metadata, date scope, and data basis. An example badge must remain visible for demo data.
- Baseline performance may be shown when supplied. Proposed-filter performance belongs in comparison unless the API explicitly supplies a suitable measured unseen evaluation; demo comparisons remain labelled illustrative.
- Findings need real hypothesis/evidence IDs. Do not manufacture anchor dates or causal news stories from aggregate findings.
- Keep the original strategy unchanged and explain that a filter changes activation or allocation only.

### Conditions

- Use the supplied regime rows and their `trades`, `net_return`, confidence interval, and evidence IDs.
- State whether the values are training/history evidence and keep the exact window visible. Small samples should remain visibly uncertain.
- Do not claim that a historical association is a validated rule.

### Evidence / agent reports

- Keep report identity separate from the selected strategy identity. A native investigation may describe a different fixture strategy.
- Preserve source/provenance, mixed model/fallback status, holdout-access warning, rejected explanations, all trial rows, candidate comparison rules, requested evaluations, and evidence payloads.
- Raw tool arguments and output may be behind a disclosure. Never present an unstructured chain-of-thought stream as the product experience.

### Compare

- Use exact chronological labels from `windows`: train, validation, and test. Prefer “Learn / Choose / New-data test” only when the exact dates remain available.
- Keep series identity stable: original, simple rule, proposed filter, cash. Use supplied baseline values and no invented drawdown timeseries.
- Show “How certain?” only where the backend supplies an uncertainty estimate for that exact comparison. Regime confidence intervals are not automatically policy-performance intervals.
- A measured paper-review action requires the actual policy state. A demo may offer a clearly labelled rehearsal, never a validation claim.

### Practice / observe

- Current paper plans are saved protocols. Show duration, policy ID, mode, approval time, and planned/not-started status.
- Do not render a 14-day timeline, simulated observations, “day N”, live updates, or a paper equity curve until a real observation contract exists.

## Motion and accessibility guardrails

Use the creative brief's M01–M36 and B01–B10 as a vocabulary, but tie every transition to a real event. Charts must retain their dimensions while loading, use actual timestamps, preserve a selected date across related views, and expose a semantic “View data” alternative. `prefers-reduced-motion` and an explicit Motion setting must remove nonessential movement. Focus must return to the trigger when a menu, editor, evidence dialog, or approval surface closes.

The redesign should be checked at 320, 390, 768, 1024, 1440, and 1920 pixels. The old light sidebar/card styling should not leak into the new surface, but accessibility comes before exact colour matching: warm text and controls still need ordinary contrast, visible keyboard focus, and 44px touch targets.

## Verification before merge

Verified locally on 7 November 2026:

- Production build, including TypeScript and prerendering, passes.
- API suite: 28 passed, with two existing FastAPI startup deprecation warnings.
- Browser: direct landing file picker → preview and mapping → saved strategy → retained success step; cancel returns to the landing screen.
- Browser: native agent report opens with source/model labels; example paper-plan approval saves and displays the correct frozen strategy identity.
- Browser: chart keyboard selection, pin/move/Escape, date persistence across views, data table, and downloaded CSV verified. Intraday readouts retain UTC timestamps.
- Browser: Back and reload restore the selected view; base `/` stays on the entry screen. Reduced motion produces the complete static example curve.
- Entry, Overview and Observe checked at 320, 390, 768, 1024, 1440 and 1920 pixels without page overflow. Chart axes remain 12px and the SVG uses measured container dimensions.
- Test data created locally: `UI walkthrough sample` (five rows from the checked-in positions template) and an illustrative paper plan. Neither is live market performance.

The list below remains the regression checklist. Full screen-reader auditing and every network-failure case have not been exhaustively tested.

1. `npm run typecheck`
2. `npm run build`
3. `.\\.venv\\Scripts\\python.exe -m pytest tests/api -q --basetemp .pytest-tmp-redesign`
4. Open the empty workspace and confirm the sparse entry shows only the seeded demo playback, with an explicit illustrative label; pause/replay and reduced-motion behavior must not add or invent values. Canceling import must return to this same entry surface.
5. Drag a supported fixture onto the entry surface, map its real columns, and confirm the saved strategy appears without demo metrics.
6. Open a seeded demo and confirm its data basis remains illustrative.
7. Open the native agent report from Evidence, switch reports, inspect a finding, inspect raw evidence, and confirm provenance/model/fallback/holdout labels.
8. Save a practice plan only after explicit approval and confirm it appears as planned/not started with its frozen snapshot when supplied.
9. Verify that no new UI claims a paper runner, live trade, market-context timeseries, cancellation, or measured result that the API did not return.
