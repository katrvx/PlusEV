# Lane B — Agents / Context

Owner: Kate. Implements AGENTS.md Lane B against the project spec. Runs today without Lane A, using a clearly-labelled synthetic stand-in in `fixtures/lane_a_stub.py` that implements the same interface Lane A promised.

## Output interface

```python
from packages.research_agents.investigate import investigate
report = investigate(experiment_id)        # -> InvestigationReport (pydantic), JSON via report.model_dump_json()
```

`InvestigationReport` contains: `verdict` (`candidate_for_frozen_test` if an agent gate earned one sealed look, else `INCONCLUSIVE`; the strategy-level KEEP / ACTIVATE / KILL decision is Lane A's arbiter's, see `docs/INTEGRATION_DECISIONS.md`) with `verdict_basis`, `champion_policy_id` (at most ONE agent policy), validation always-on and cash references, ranked hypotheses with evidence ids, gate proposals, critiques, the full trial log (every attempt incl. refused ones, keyed by spec hash), candidates with validation delta vs always-on, vs cash and vs the simple rule, CI and in-position allocation mix (critic text in reasons is prefixed `critic:`), test requests for Lane A, limitations, every piece of evidence (raw tool output), `agent_failures`, `n_distinct_agent_policies`, `n_policies_tried`, `holdout_accessed`, and `agent_mode` (`llm`, `llm_with_fallback`, `deterministic_fallback`).

## What's built

| Step (AGENTS.md) | Where | Status |
|---|---|---|
| 1 Pydantic output models | `packages/research_agents/models.py` | done |
| 2 Four allowlisted tools: `regime_performance`, `cost_attribution`, `news_context`, `test_gate_train` | `packages/research_agents/tools.py` | done |
| 3 Diagnostic agent | `packages/research_agents/agents.py` | done (PydanticAI) + deterministic fallback |
| 4 Critic agent | same | done + fallback |
| 5 Gate proposer with whitelist | same + `allowlist.py` | done + fallback |
| Agent 4: context (sentiment) | `context.py` (tool, code), `agents.py` (agent), `fallback.context` | done: Fear & Greed around the 4 best and 4 worst train weeks, with base rates and binomial p-values; no news archive, so no news agent |
| 6 Semantic news labelling with first-seen timestamps | `news.py`, `labeller.py` | models, point-in-time store, LLM + lexicon labellers; no news data yet |
| meta_policy: rule gate + LightGBM gate | `packages/meta_policy/` | done |

## Guardrails, enforced in code (and tested)

- **No held-out labels.** Every tool refuses the test split; a news window that reaches into the test period is refused; LightGBM refuses to fit/calibrate on test; any attempt sets `holdout_accessed=True` in the report.
- **Claims link to evidence.** Every tool output is stored with a content-addressed `evidence_id`. Output validators make the LLM retry if it cites an id no tool produced.
- **Allowlisted gates only.** `threshold_gate`, 1–2 conditions, features `momentum_24h / momentum_7d / realized_vol_7d / atr_14 / price_drawdown / volume_zscore / fear_greed / news_sentiment`, allocations `{0, 0.5, 1}`, thresholds must be training-quantile values, features need ≥90% coverage. Anything else is refused and logged.
- **Budget.** At most 12 agent train tests per investigation; the arbiter's validation runs never consume it. All attempts disclosed.
- **Agents see train only.** Validation is used only by the arbiter (code); the critic sees validation results through the trial log.
- **Claims are checked, not just ids** (`verify.py`). EVERY text field of all three agents: numbers must be copied from the cited evidence (print rounding, and never more than 1% of the value; `%` and `bp` are the only rescalings; `.5`, Unicode minus signs and e-notation integers are numbers too; a written zero needs an exact zero; integers above 10 must equal an evidence count; explicit signs must match; number words and `3.5x` count as numbers; only the CI label `90%` is free). Regime conditions must exist in the cited rows; `high` confidence needs |mean| > CI width; critiques must cover exactly the real proposals, cite each gate's own evaluation, and may not 'approve' while listing blocking fragility.
- **Results keyed by spec hash**, so two proposals with the same name can never share a result; duplicate ids are rejected.
- **Robust to LLM failure.** Bad tool arguments become retries; any LLM stage failure falls back to the deterministic agent and is listed in `agent_failures`.
- **Missing data is conservative**: a row with a missing gate feature gets min(allocation_when_true, allocation_when_false).
- **No strategy changes, no code execution, no orders.** Gates output multipliers only.
- **News is point-in-time.** Visible only if `first_seen_at <= decision cutoff`; coverage reported; never used in a gate unless coverage ≥ 90%.
- **The arbiter is code.** Pre-registered rule (docstring of `investigate.py`): an agent proposal is eligible iff on validation it beats always-on (finite delta > 0, finite CI), beats cash (own net return > 0), is not degenerate (no multiplier on >= 95% of IN-POSITION bars) and is not vetoed by the critic. The eligible one with the highest validation delta is the single champion; only it plus the competitors (simple rule, LightGBM, and Lane A's regime filter when it selected at least one bucket) go to the frozen test. No champion -> `INCONCLUSIVE`, and `verdict_basis` tells Lane A's arbiter when the unchanged strategy loses to cash.
- **Timeouts are honest.** Stage timeout, request timeout and request limit; tool calls that finish after their stage ended are logged (status `error`, note `abandoned: ...`) and disclosed. `agent_mode` stays within the Lane C contract (`llm` / `llm_with_fallback` / `deterministic_fallback`).
- **LightGBM is out-of-sample on validation**: fitted on early train, calibrated on late train, band preselected around the calibration base rate.

## Adversarial review

Two independent agents attacked Lane B on 7 Nov. Round 1: 18 findings (17 reproduced). Round 2, after the first real Gemini 4 Argon run: 17 findings (16 reproduced), incl. a claim verifier that accepted almost any number, '95% CI' written 4 times in the Argon report, mixed return conventions in the stand-in ('strategy underperforms always-on'), and no comparison with cash. All critical/high findings of both rounds are fixed with regression tests (68 tests after round 2). Note: with the corrected bootstrap (2000 draws, seeded by spec), the stand-in's 'high volatility' effect on train is borderline (90% CI upper bound just above zero), so the strict deterministic fallback now proposes no gate; we did not retune the synthetic data to change that. Remaining known gaps: no news agent (the context agent works on Fear & Greed only), no `run_bootstrap` tool (CIs come from Lane A), no news data, and the default loader in tests is the synthetic stand-in.

Round 3 (7 Nov evening) started from the first full `mode=llm` runs on Lane A's real BTCUSDT data with Gemini 4 Argon. In the first one (19:24, not committed), all three agents ran with no fallback, and the holdout was not accessed. The verifier made the proposer and the critic retry three times: once for an invented number, and once for real numbers cited from the wrong gate's evidence. The critic found that one gate switched more often than always-on (70 vs 50 on validation), that its validation Sharpe failed the proposal's own falsification test, and that the other gate's validation gain came from lower exposure in a falling market. Both gates were rejected; neither beats cash on validation. Fixed after that run:
- the verifier no longer rejects numbers the agents were given (`20` in the instructions, `24`/`72` in `btc-trend-24-72-demo`);
- numbers glued to `h`/`d` (`73h`) are now checked;
- agents are told to round to 3–4 significant digits;
- default timeouts are now 180 s per request and 400 s per stage (Argon's critic hit the old 90 s);
- Lane A's new `momentum_7d`, `atr_14` and `price_drawdown` are allowlisted, and only where the loader reports coverage.

Lane A meanwhile fixed the four contract gaps Lane B reported: compounded cost rows (`switching` is 0 for the unchanged strategy), in-position `allocation_mix` with `n_decisions`/`n_in_position`, a bootstrap seeded by the spec body with 2000 draws, and LightGBM calibrated on late train with its seed and model hash in `spec()`. With the old 0.45/0.55 cut that LightGBM sat at 0.5 on 99% of in-position validation bars, and Lane B flagged it as degenerate. Lane A then switched to a band of the train-tail base rate ± 2 points. It is no longer degenerate, but it loses: −17.7% vs always-on on validation and 0/3 on Lane A's refit walk-forward.

Those morning runs used Lane A's earlier Nov 2024 – Oct 2026 window. The committed artifacts are now the reruns on the 2018–2026 book; see "Two strategies on real data" below.

A third independent review (round 3) then attacked everything above: 13 findings, all reproduced. Critical: after the walk-forward change, rule (c) (no degenerate gate) only ran when fold results existed, so a degenerate gate approved by an LLM critic could reach the sealed test on a runner without folds. Fixed, with a regression test on the stand-in runner. Also fixed:
- verifier leaks: `.9876`, a Unicode minus, numbers like `0.3` passing for 0.251, `2e2 trades`, a bare `20`, written zeros, and free numbers drawn from upload ids;
- real-data runs were written under the synthetic fixture's file name;
- the regime filter posed as a competitor when it had selected no buckets (it is always-on, and is now reported as such);
- failed folds were described as missing folds;
- trial records now carry a structured `fold`;
- Lane A's notes, which quote the sealed-test verdict, are dropped from what agents can see.

Round 4 (8 Nov, after the reruns on the 2018–2026 book): 16 findings, 15 reproduced. Three change what we can claim, and are disclosed rather than fixed:
- **The test window was not unseen by the team.** Lane A's test period (2025-02 → 2026-10) overlaps the earlier two-year window we developed on. On it, the agents had already proposed a similar idea for mean reversion (cut size in calm markets). The single look is pre-registered and recorded, but it is not a look at data nobody had seen. A clean test needs data after 2026-10-31.
- **Lane A's arbiter never scored the Lane B champion.** Its KILL is for the strategy. Under its rule, the champion would have qualified as MODIFY even with a −29% net, because MODIFY does not require beating cash. That is reported to Lane A. We had not pre-registered how a test result maps to a Lane B verdict; by our own selection bar (beat cash), the champion fails on test.
- **The improvement is mostly lower exposure.** The champion is at half size on about 87% of bars. A constant half size gives +11.1 pp on validation, and on the research period it beats the champion. Every report now carries a constant-half-size reference, and each agent gate shows its delta against it.
- **The critic acted as a selector.** It vetoed a sibling gate with the same condition (size 0 instead of 0.5) that scored higher on validation.

Fixed in round 4:
- the sealed look is ledgered on disk by spec hash (`experiments/frozen_ledger.json`), and only `scripts/frozen_look.py` takes it, from a committed report; `--frozen` no longer re-runs an investigation and looks;
- the context verifier ties `moderate` to a primary tally at p < 0.05, checks the named weeks, catches more causal wording and allows negated caveats;
- quantile and allocation levels are citable only when named as such;
- the 20-trade threshold phrasing requires the word "trades";
- best and worst weeks no longer overlap;
- bad loader data no longer crashes the context stage;
- the docs are corrected (pp instead of %, "trailed by 48 pp" instead of "lost 48%").

## Agent 4: context (`context.py`)

The spec's fourth agent is a context and news analyst. There is no news archive with first-seen timestamps, so this agent works on market sentiment (Fear & Greed), which Lane A joins point-in-time (each daily value as of its next-day availability). Code (`sentiment_episodes`, TRAIN only) picks the unchanged strategy's 4 worst and 4 best non-overlapping weeks (168 bars). For each week it records the Fear & Greed level, its 7-day change, and whether a greed-to-fear or fear-to-greed flip (across 50) happened in the 3 days before the week started. It also gives the train base rate of such flips and a one-sided binomial p-value. The agent writes findings that cite this evidence and name the weeks they use. The verifier rejects:
- causal language ("because", "caused", "led to"…);
- invented numbers;
- unknown episode ids;
- strength `moderate` unless a cited p-value is below 0.10.

The findings go to the proposer as context only; gates are still based on the diagnostic hypotheses. Without a sentiment series (the stand-in), the stage is skipped and disclosed.

Only the two primary tallies (worst weeks after a greed-to-fear flip, best weeks after a fear-to-greed flip) can support a `moderate` finding, and only at p < 0.05, which is 0.10 Bonferroni-corrected for the two; the other two tallies are descriptive. A finding that names a tally must set `tally`, and the weeks it names must carry that flag. On the 2018–2026 book neither primary tally is notable for either strategy. In the trend report, Argon labelled a non-primary tally `moderate`: 2 of 4 best weeks followed a greed-to-fear flip, p 0.048 against base rates of 0.093–0.096. One of those weeks is in early 2018, when flips were about twice as frequent. Corrected for four tallies, that finding is weak, and the verifier now refuses that label (round 4).

## Bad luck vs broken (`health.py`)

Spec section 8: a poor result alone is not proof that a strategy broke. Code, not an agent, cuts the unchanged strategy's validation period into 14-day blocks. It compares each block with Lane A's train-only 14-day range (5th to 95th percentile of block-bootstrapped train paths). About 5% of blocks should fall below that range by chance. If more do (one-sided binomial p < 0.05), the result is `outside_training_range`; otherwise it is `within_training_range`. It also checks which assumption changed between train and validation: exposure, turnover per bar, cost per bar, bar volatility (ratio outside 2/3–3/2), and how often each regime occurs (total variation ≥ 0.25). The thresholds are fixed in the module. Because the check reads validation, only the critic can call it (`strategy_health` tool) and it appears in the report (`strategy_health`, plus a line in `verdict_basis`). The fallback critic notes when the regime behind a gate's feature shifted.

On the 2018–2026 book: for trend, 43 of 45 validation blocks fall inside the range and 2 above it. For mean reversion, all 45 fall inside its research range (−16.2% to +12.4% per two weeks), and over that research period it lost 90%. It behaves as it always did, and it always lost money. Lane A's arbiter says KILL for the strategy. On the earlier 2-year window, the check had separated the two (10/10 inside vs 3/10 below).

## Two strategies on real data

Lane A's 2018-02 → 2026-10 hourly BTCUSDT book (research → 2023-05, validation → 2025-02, sealed test → 2026-10). Both investigations ran on Gemini 4 Argon (`mode=llm`, no agent failures, holdout not accessed).

| | `btc-trend-24-72-demo` | `btc-meanrev-48-demo` |
|---|---|---|
| Always-on | research +276%, validation +134% | research −90%, validation −19% |
| Strategy health (validation) | `within_training_range`, 43/45 blocks inside, 2 above. Sentiment, volatility and cost per bar changed | `within_training_range`, 45/45 inside. Its normal range is a losing one |
| Context agent | 2 of 4 best weeks followed a greed-to-fear flip (p 0.048; a non-primary tally, so weak after correction, though the report says `moderate`); worst weeks show no flips | Sentiment does not separate good and bad weeks |
| Agent gates | 3 proposed, all vetoed. `fear_greed > 28` beat always-on by 32 pp on validation, but it was on 97% of the time after the sentiment shift (fear 51% → 10%), and on the first research fold it trailed always-on by 48 pp (+5.1% vs +52.8%) | Champion `vol_median_05_1` (half size when `realized_vol_7d` ≤ research median): validation +26.8 pp vs always-on (90% CI +1.1 … +40.9), +7.3 pp vs cash, 3/3 folds, critic approved. Constant half size alone: +11.1 pp |
| Test (one look) | Lane A arbiter: INCONCLUSIVE | Gate vs always-on +27.3 pp (90% CI +15.3 … +36.2), max drawdown 60.4% → 36.2%, average size 0.55× always-on, net −28.9%. Lane A's arbiter scored only its own candidates: KILL for the strategy |

Reports: `experiments/investigation_argon_lane_a.json`, `experiments/investigation_argon_meanrev.json`. The sealed look is `experiments/frozen_look_btc-meanrev-48-demo.json`. It was taken after the report that chose the champion was committed (`ad3dff1`).

## Run on Lane A

The default loader is still `fixtures/lane_a_stub.py`, so `tests/test_lane_b.py` does not need the Binance snapshot.

```bash
python3 scripts/run_investigation.py --lane-a --fallback
python3 scripts/run_investigation.py --lane-a --fallback --experiment-id synthetic-btcusdt-1h-v1
python3 scripts/run_investigation.py --lane-a --fallback --frozen
# --lane-a writes experiments/investigation_lane_a_<strategy>_<mode>.json by default (never the synthetic fixture's name)
KOK_AGENT_MODEL=google:gemini-4-argon GEMINI_API_KEY=... python3 scripts/run_investigation.py --lane-a   # LLM agents on real data
```

`load_for_lane_b` returns train and validation metrics only. `GateRunner.evaluate` refuses `test`. The development view drops the note that quotes the sealed-test verdict; `redact` still clears every note before a tool sees the result. `--frozen` is the one sealed look, and only for the champion the arbiter accepted. The simple-rule competitor is Lane A's own rule when the loader provides `runner.rule_spec` (flat when the condition fails). The arbiter scores it directly, so the fixed momentum threshold of `0` does not have to sit on the agent quantile grid. Lane A's train-selected regime filter (`runner.regime_spec`) is a third competitor. Each agent gate's reasons show its validation delta against that filter, and the verdict basis states the filter's own result. Like the simple rule, the filter is a reference and not a veto, because the selection rule was registered before any run.

Walk-forward: every agent gate and competitor is also scored with Lane A's `GateRunner.evaluate_folds`. It uses the same three expanding train folds and the same 2-bar embargo as Lane A's LightGBM walk-forward. Each fold is logged in the trial log (note `walk-forward fold k`, split `train`) and stored as evidence the critic can cite. The candidate reasons show "beats always-on on k/3". The fallback critic flags a gate that wins on fewer than half the folds. Thresholds come from quantiles of the whole train window, so the folds are a stability check over train sub-periods, not unseen data, and they do not change the pre-registered selection. The fitted LightGBM has seen all of train (fit plus calibration), so it is not re-scored on the folds. Its line uses Lane A's own walk-forward, which refits the model before each fold (on real data: 0/3).

## Run

```bash
pip install "pydantic-ai-slim[google]" lightgbm scikit-learn pandas numpy pytest
python3 -m pytest -q tests/test_lane_b.py          # 140 guardrail + regression tests
python3 scripts/run_investigation.py --fallback     # deterministic agents
KOK_AGENT_MODEL=google:gemini-3.8-flash GEMINI_API_KEY=... python3 scripts/run_investigation.py   # LLM agents
```

## What Lane A needs to provide (to replace the stand-in)

See `packages/contracts_lane_b/__init__.py`:
1. `ExperimentResult` with `per_regime` rows (split, regime_feature, bucket, counts, mean net return, block-bootstrap CI, costs), `costs`, `baselines`, `coverage`, `windows`.
2. A `GateRunner.evaluate(policy_spec, split) -> GateEvaluation` that simulates the gate on train/validation with next-bar fills and switching costs, returns compounded net returns, a paired block-bootstrap CI of the delta and the allocation mix, is deterministic for the same input, and refuses `split="test"`.
3. Training-window quantiles for the allowlisted features (the threshold grid).
4. A loader `experiment_id -> (ExperimentResult, GateRunner, train_quantiles, NewsStore|None, LGBMGate|None)` passed to `investigate(..., loader=...)`.

## What Lane C reads

`experiments/investigation_*.json` = `InvestigationReport`. Useful views: hypotheses with confidence and evidence; trial log table (show refused attempts too); candidates with reasons; limitations; `agent_mode` badge ("deterministic fallback" vs model id); evidence drawer keyed by `evidence_id`.

## Open questions for the team

- Model access: can our code call Argon via an API, or only through Antigravity? If not, free-tier Gemini API with no billing; otherwise fallback mode.
- Lane A's exact field names for regimes (`trend_regime`, `vol_regime` assumed here).
- News source for the chosen window (GDELT DOC covers ~3 months only).
