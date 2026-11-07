# 10 · Build plan

Hacking: Sat 7 Nov 09:00 → Sun 8 Nov 18:00. Docs finished Sat ≈15:30. **≈26.5 hours of build.** Judges score from the repo and deck; only the top 3 pitch live. So the deck and the evaluation tables are deliverables, not afterthoughts.

## Roles

| # | Owner | Area | First deliverable |
|---|---|---|---|
| 1 | — | **Data + regime labeller** `[code]` | `regimes.parquet` for the universe, no-look-ahead test green |
| 2 | — | **Simulator + evaluation** | strategy zoo emitting trade CSVs; `eval/run_all.py` skeleton |
| 3 | — | **Judge** (strongest in stats) | X-ray A1–A4 on a sample CSV; then B1–B5 |
| 4 | — | **Agents** (Gemini/ADK) | sentiment labeller with cache + anonymiser; then lens agents + ledger |
| 5 | Kate | **Lead: architecture, risk controls, audit log, explainer check, deck** | repo scaffold, `audit/`, `risk/`, deck skeleton |
| all | | **UI** from Sat 22:00 (owner 1 and 4 move to UI once their pipelines run) | |

Rule: nobody blocks on anybody. Every module has a fake-data fixture so it can be built in isolation. Interfaces are the trade CSV schema and the judge JSON schema; freeze both by Sat 16:30.

## Timeline

### Saturday

**15:30 – 16:30 · Scaffold and contracts**
- `uv init`, `pyproject.toml` from [03](03-tech-stack.md), ruff, pytest, GitHub Actions.
- Freeze two schemas in `barometer/schemas.py`: `Trade`, `JudgeVerdict` (X-ray and Kill-or-Keep variants). Everyone codes against them.
- Owner 1 starts the Yahoo + Binance pull. Owner 4 gets Gemini keys working with a structured-output hello-world.
- Kate: `audit/log.py` (hash chain + verify), `risk/controls.py` stubs.

**16:30 – 19:00 · Thin thread end to end**
- Owner 1: regime features for SPY only; `ASOF JOIN` tagging; `features_as_of` test.
- Owner 2: `sim/zoo.py` with mean-reversion alive/noise/dies; one CSV of each.
- Owner 3: X-ray A1 (conditional P&L + stationary bootstrap) on the sim CSVs; print the table.
- Owner 4: GDELT pull for SPY themes (one year) → anonymiser → sentiment labeller → Parquet.
- Kate: `risk/controls.py` real; the explainer number-check; deck skeleton with the rubric mapping.
- **19:00 checkpoint:** a sim CSV goes in, a tagged table and a conditional-P&L table come out. If not, cut scope now (drop hourly, drop crypto), not at midnight.

**19:00 – 22:00 · Make the judge real**
- Owner 3: A2 BH correction, A3 sealed holdout with receipt, A4 filter test. Then B1 drawdown percentile.
- Owner 2: full zoo (4 families × 3 truths × universe), `eval/run_all.py` runs E1 on the dev set.
- Owner 1: all regime features, HMM, event calendar; full-universe `regimes.parquet`.
- Owner 4: lens agents in ADK (or pydantic-ai, decide by 18:00) + ledger; run the swarm on the sim strategy descriptions.
- Kate: explainer prompt + check; integrate audit log into judge and ledger.
- **22:00 checkpoint:** E1 numbers exist for the dev set, even if ugly. **UI decision:** React or Streamlit. If nothing renders yet, Streamlit.

**22:00 – 02:00 · Kill or Keep + UI**
- Owner 3: B2 conditional drift, B3 decomposition, B4 e-process via `ville` + fallback, B5 e-detector. Calibrate ARL on alive runs.
- Owner 2: E2 harness (DD-20, 3-loss, Barometer rules); E3 logging of predicted vs. actual N.
- Owners 1 + 4: UI. Price chart with regime bands and trade markers (lightweight-charts), heatmap (ECharts), live feed + verdict panel, override ledger panel.
- Kate: risk controls wired to UI; override ledger scoring; deck slides for problem, user, architecture.
- **Sleep in shifts from 00:00.** Two people down at a time, 3 hours each. Nobody pulls an all-nighter; a tired judge-coder ships a wrong bootstrap.

### Sunday

**02:00 – 08:00 · Fill and harden**
- Remaining judge pieces, B6 posterior with printed prior.
- Property tests from [05 Part D](05-judge-and-stats.md). They are the credibility of the judge; a judge that passes its own noise test is worth a slide.
- Memorisation guard run (E5). Whatever it says, it goes in the deck.
- README quickstart that actually works on a clean clone (`uv sync && uv run demo`).

**08:00 – 11:00 · Final evaluation run**
- Owner 2 runs `eval/run_all.py --set eval` on the **evaluation set, first time**. Commit hash recorded. Tables and figures into `eval/results/`.
- Everyone else: demo data (one alive bot, one dying bot), demo script rehearsal, backup screen-recording of the demo.
- **Feature freeze 11:00.** After this only bugs, deck, README.

**11:00 – 15:00 · Deck**
- Deck per [11](11-demo-and-pitch.md). Every claim has a table or figure from `eval/results/`. Numbers, intervals, counts (proposed → survived → confirmed).
- Record the 90-second demo video. Live demos break.
- Repo: README, licence, data manifest, `.env.example`, Actions green.

**15:00 – 17:00 · Submit early**
- Submit by 17:00, not 17:58. Then rehearse the 4-minute pitch three times in case of top-3.

**17:00 – 18:00 · Buffer.**

## Scope guards (decide at the checkpoint, not later)

| If by… | …this isn't true | then |
|---|---|---|
| Sat 19:00 | a sim CSV → tagged table → conditional P&L works | drop hourly bars and crypto; daily US equities only |
| Sat 22:00 | E1 runs on the dev set | drop HMM and news-volume features; keep vol, trend, event window, sentiment |
| Sat 22:00 | React renders anything | Streamlit |
| Sun 02:00 | B3 decomposition works | report execution+signal jointly, say so in the deck |
| Sun 02:00 | swarm runs | single lens agent + default panel; say "swarm is the obvious extension" |
| Sun 08:00 | Kill or Keep works end to end | **ship X-ray alone.** It is a complete, honest project. Deck reframes to "before you trust it". |
| Sun 08:00 | memorisation guard ran | run it on 50 days only; report that |

## Definition of done

- `uv sync && uv run barometer demo` on a clean clone produces the X-ray heatmap and a Kill-or-Keep verdict for the demo bots.
- `eval/results/` contains E1–E3 tables with intervals from the evaluation set, with the commit hash.
- Deck has: user, failure on screen, architecture with code/LLM split, the three counts, E1–E3 numbers, limitations, data licences.
- Audit log verifies.
- Public repo, README, licence, Actions green.
