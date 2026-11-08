# Creative direction implementation map

This document is the integration guardrail for the redesign described in `KEEP_OR_KILL_CREATIVE_DIRECTION_PROMPT.md`. The redesign keeps the existing import, storage, evaluation, report, evidence, and paper-plan interfaces as the source of truth. Strategy-definition builder work remains optional and draft-only; it must not be presented as a new evaluator contract.

## Latest surface direction (user steering)

Use warm cream, deep plum typography, an orange bull and a lavender bear. This supersedes the earlier electric-blue direction. The shared tokens in `apps/web/src/components/redesign/design-system.css` own the palette, including input boundaries, chart series, focus states, tooltips and dialogs. Keep bold neutral Inter headings, generous whitespace, substantial smooth chart strokes and concise explanations beside the evidence.

The visible product is **+EV**, with its own SVG wordmark and browser icon. The judge flow is Verdict → Conditions → Evidence → Compare → Paper plan. Only Verdict uses the full decision hero. Secondary pages use a quiet, scoped decision row so the current page's question is the main focus. Each step emphasizes one next action; source access and the opt-in help mascot remain secondary.

For native reports, the overview leads with “Unlucky or broken?”, the supplied `strategy_health` blocks and a large explanatory mascot. The mobile scene appears before the detailed chart so the explanation is visible early. The chart plots the actual dated validation returns against the supplied training range; it does not invent an equity curve. Inside the range does not mean profitable. Legacy experiments retain their actual equity, keyboard/touch inspection, date state and exports. Exact source details remain accessible.

The entry surface is a minimal scroll story beginning with “Good strategy. Wrong market?” and the generated mascot duo. It moves through changing market contexts, research inputs, challenged explanations, and “Don’t guess when. Test it.” The upload and example actions remain available at the start and end. `strategy-entry.tsx` replays the seeded demo experiment’s recorded `equity` points in the final scene, labels it as example data, and preserves pause/replay and reduced-motion behavior. File selection, drag-and-drop, Try an example, and Your workspace remain functional. The playback must never be reused for imported strategies or presented as measured market performance.

All 24 generated poses are connected to contextual states through the shared `mascot.tsx` component and asset manifest. Large characters form a primary explanatory scene on each screen, with short accessible HTML speech bubbles; the artwork itself has no enclosing card. Desktop cells are roughly 340–380px and mobile cells 280–300px because the original atlas includes transparent padding. On phones, a character peeks inward from the right edge once its explanation enters view. Entrances, bubble arrival and a brief two-cycle speaking motion stop in reduced motion. Original reference images remain under Git-ignored `artifacts/` and are never data sources.

The primary verification input is a strategy's timestamped positions, supplied as CSV/Parquet or eventually through a platform API. Strategy source code stays private. The existing position/trade importer validates rows, mapping, costs and provenance; it does not infer rules or attach a history record to another strategy definition. Completed trades remain diagnosis-only. The optional rule form / JSON builder supports bounded EMA crossover and RSI mean-reversion definitions as drafts only: definitions are versioned and hashed, but do not create signals, attach market data or produce measured results. See `STRATEGY_INPUTS.md` for the precise input boundaries.

The judge path opens a real recorded example, reads the verdict, inspects conditions and agent evidence, compares the sealed metrics, then reviews the approval requirements. This report cannot save a paper plan: the original strategy was marked Kill and the gate has no new approved candidate verdict. The local default reports are the recorded Argon artifacts `investigation_argon_lane_a.json` and `investigation_argon_meanrev.json`, both served as `synthetic: false` and carrying `strategy_health`. Keep “not proven” visible when a particular evaluator result is unavailable. Legacy fixture reports remain explicitly synthetic; never fill a gap with invented scores, regime timelines, holdout observations or paper-test days.

The frozen mean-reversion look (`frozen_look_btc-meanrev-48-demo.json`) records a +27.3 percentage-point gate-versus-always-on difference with a 90% interval of +15.3 to +36.2 and a drawdown change from 60.4% to 36.2%. The gated book itself is −28.9% with an interval containing zero, so the difference is not a profitability claim. The published **KILL** belongs to the always-on book, whose drawdown exceeded the cap and whose net interval was below zero; it is distinct from the gated-book comparison. `score_frozen` did not rerun the arbiter.

`workspace-guide.tsx/css` provides an opt-in “Explain this page” walkthrough. A large mascot and HTML speech bubble appear with a hand-drawn arrow, while the page dims around a real target. It supports step navigation, Escape, focus trapping/restoration, temporarily inert background content and static reduced-motion rendering. It never represents agent progress or changes research data.

Research and entry charts use `chart-path.ts` for shape-preserving cubic interpolation through supplied points, with a thicker primary stroke. Smoothing changes drawing only: observations, tooltips, exports, metrics, and API contracts are unchanged. All import, strategy, experiment, native report, report download and paper-plan integrations remain intact.

## Animation and shared controls

Official React Bits `AnimatedContent` and `Magnet` are vendored in `apps/web/src/components/react-bits`, with pinned upstream source and license notices. GSAP runs the restrained 14px page entrances; Motion animates the shared navigation selection. `redesign/ui-motion.tsx` centralizes timings and the existing motion preference. The operating system reduced-motion preference always disables the new motion; magnetic controls also stop on touch and keyboard focus. Display settings offer System and Reduced; obsolete Full preferences fall back to System. Financial figures are never counted through fictional values.

The primary action uses `kk-primary-button` across entry, strategy, overview, evidence, comparison and plan approval. Colours, rounded corners, focus rings and touch targets come from `design-system.css`. The overview curve has a quiet orange area fill; it preserves the supplied points and data gaps. Effects must remain short, respect reduced motion and never gate access to content.

### Scroll and text choreography

- `kinetic-text.tsx/css`: GSAP masked word entrances (700ms with 45ms stagger), used inside semantic headings. Text stays readable before hydration and after cleanup. No financial values use this effect.
- `research-story.tsx/css`: a sticky desktop timing scene with a moving focus window and headline swap, followed by open research, challenge and conclusion sections. Mobile uses normal stacked flow. Conceptual market shapes are illustrations, never timestamps or returns attached to the strategy; findings come only from the supplied demo experiment.
- `story-signal.tsx/css`: a labelled process illustration with three inputs converging through a research lens. Its stroke draws, lens movement and check marks are linked to scroll; they do not represent live agent progress or measured performance.
- `strategy-entry.tsx/css`: immediate upload/example controls, a recorded chart playback in the conclusion that pauses outside the viewport or in a hidden tab, and a focusable normal-scroll link into the research story. Import and resume callbacks are unchanged. Playback sorts valid observations, resets when the example changes and explicitly handles unavailable data.
- GSAP owns text and scroll visuals, Motion owns navigation selection, and Magnet only moves its inner action element. Animation must never delay an API operation or prevent access to evidence.

Reference research: [Revolut](https://www.revolut.com/) for bold hierarchy and concise calls to action; [Linear](https://linear.app/) for product-led storytelling; [React Bits Split Text](https://reactbits.dev/text-animations/split-text) for masked text entrances; [GSAP ScrollTrigger](https://gsap.com/docs/v3/Plugins/ScrollTrigger/) for scroll-linked sequencing and cleanup. These are design references, not dependencies on those products' assets or claims.

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

- Lead with “Verify a strategy” / “Import strategy positions” language. Strategy source code stays private; do not ask for executable Python or Pine.
- Keep `ImportWizard`'s focus trap, native chooser, preview request, mapping selectors, validation issue display, upload lock, stale preview invalidation, and success callback.
- Preserve the entry context when the import dialog is cancelled: cancelling from the sparse landing returns to that landing; importing from the workspace returns to the workspace.
- Timestamped strategy positions are the primary verification input. Trade history remains diagnosis-only and must not be used to reconstruct rules.
- The optional rule builder / JSON definition remains a draft-only path with no generated signals or measured result.
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

Use the creative brief's M01–M36 and B01–B10 as a vocabulary, but tie every transition to a real event. Charts must retain their dimensions while loading, use actual timestamps, and preserve a selected date across related views. Detailed research screens expose semantic data alternatives; the overview omits the View data block at the user's request. `prefers-reduced-motion` and an explicit Motion setting must remove nonessential movement. Focus must return to the trigger when a menu, editor, evidence dialog, or approval surface closes.

The redesign should be checked at 320, 390, 768, 1024, 1440, and 1920 pixels. The old light sidebar/card styling should not leak into the new surface, but accessibility comes before exact colour matching: warm text and controls still need ordinary contrast, visible keyboard focus, and 44px touch targets.

## Current pass — verified locally, 8 November 2026

The combined typecheck and production build pass. The API suite passes 44 tests with two existing FastAPI startup deprecation warnings. The production judge flow was clicked through from Try an example → Verdict → Conditions → supporting source → Evidence → Compare → approval requirements. The report stays read-only, with its approval checkbox and save action disabled. Source code remains private; position rows are a separate input; completed trades are diagnosis-only; optional rule JSON stays draft-only; plans remain saved/not running; and recorded Argon `strategy_health` reports remain tied to their exact strategy/report identity.

Desktop and mobile captures are in the ignored `artifacts/positioning-redesign/` directory, with the latest check record in `VERIFICATION.md`. Responsive checks at 320, 390, 768, 1024, 1440 and 1920px found no page overflow in the checked surfaces. The guide traps/restores focus, makes the background inert, and has no active animation in Reduced mode. System mode restores the scroll-driven text and chart transitions. Evidence dialogs, source-browser arrow keys, report switching, chart date keyboard state, Back navigation and the report download were exercised. No console errors occurred in the final production walkthrough.

The detailed report now leads with the latest recorded conclusion and a large mascot. Matching strategy identity and scoped decisions remain visible; model/source metadata and research counts are secondary. Source evidence uses one selected output panel instead of dozens of accordions. All recorded arguments, payloads, trials, candidates and report identities remain accessible.

The Argon reports are recorded team artifacts and should be shown with their actual `synthetic: false`, model, holdout and strategy identities. The legacy fixture is synthetic and must stay excluded from claims about the Argon reports. The frozen look's +27.3 percentage-point comparison is not profitability evidence, and the always-on **KILL** is distinct from the gated-book result. No new result, score, regime timeline, holdout observation or paper-test day should be added to make the screens look complete.

## Verification before merge

Motion follow-up verified locally on 8 November 2026:

- Typecheck and production build pass, including static prerendering.
- Desktop timing scene changes “Different markets” to “Different outcomes” with scroll. The research diagram, evidence entrances and conclusion playback use distinct motion. Mobile at 390px stacks the story without horizontal overflow.
- Reduced motion leaves all headings and complete illustrations readable, with no sticky scroll extension. Returning to System restores playback. The story anchor moves keyboard focus into the named story region.
- Footer Explore the example opens the research overview and clears the landing story anchor. Footer Test your strategy reaches the real preview/mapping flow with the checked-in five-row positions sample; cancelling returns to the landing.
- Existing Evidence headings and navigation remain functional. This follow-up did not change API contracts or rerun the API suite listed below.

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
4. Open the entry and confirm Try an example opens the real recorded report. When no equity series is supplied, show the process cue without inventing a curve. Legacy demo playback stays explicitly illustrative. Canceling import must return to this same entry surface.
5. Drag a supported fixture onto the entry surface, map its real columns, and confirm the saved strategy appears without demo metrics.
6. Open a seeded demo and confirm its data basis remains illustrative.
7. Open the native agent report from Evidence, switch reports, inspect a finding, inspect raw evidence, and confirm provenance/model/fallback/holdout labels.
8. Save a practice plan only after explicit approval and confirm it appears as planned/not started with its frozen snapshot when supplied.
9. Verify that no new UI claims a paper runner, live trade, market-context timeseries, cancellation, or measured result that the API did not return.
