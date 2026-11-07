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
| 6 Semantic news labelling with first-seen timestamps | `news.py`, `labeller.py` | models, point-in-time store, LLM + lexicon labellers; no news data yet |
| meta_policy: rule gate + LightGBM gate | `packages/meta_policy/` | done |

## Guardrails, enforced in code (and tested)

- **No held-out labels.** Every tool refuses the test split; a news window that reaches into the test period is refused; LightGBM refuses to fit/calibrate on test; any attempt sets `holdout_accessed=True` in the report.
- **Claims link to evidence.** Every tool output is stored with a content-addressed `evidence_id`. Output validators make the LLM retry if it cites an id no tool produced.
- **Allowlisted gates only.** `threshold_gate`, 1–2 conditions, features `momentum_24h / realized_vol_7d / volume_zscore / fear_greed / news_sentiment`, allocations `{0, 0.5, 1}`, thresholds must be training-quantile values, features need ≥90% coverage. Anything else is refused and logged.
- **Budget.** At most 12 agent train tests per investigation; the arbiter's validation runs never consume it. All attempts disclosed.
- **Agents see train only.** Validation is used only by the arbiter (code); the critic sees validation results through the trial log.
- **Claims are checked, not just ids** (`verify.py`). EVERY text field of all three agents: numbers must be copied from the cited evidence (print rounding only; `%` and `bp` are the only rescalings; integers above 10 must equal an evidence count; explicit signs must match; number words and `3.5x` count as numbers; only the CI label `90%` is free). Regime conditions must exist in the cited rows; `high` confidence needs |mean| > CI width; critiques must cover exactly the real proposals, cite each gate's own evaluation, and may not 'approve' while listing blocking fragility.
- **Results keyed by spec hash**, so two proposals with the same name can never share a result; duplicate ids are rejected.
- **Robust to LLM failure.** Bad tool arguments become retries; any LLM stage failure falls back to the deterministic agent and is listed in `agent_failures`.
- **Missing data is conservative**: a row with a missing gate feature gets min(allocation_when_true, allocation_when_false).
- **No strategy changes, no code execution, no orders.** Gates output multipliers only.
- **News is point-in-time.** Visible only if `first_seen_at <= decision cutoff`; coverage reported; never used in a gate unless coverage ≥ 90%.
- **The arbiter is code.** Pre-registered rule (docstring of `investigate.py`): an agent proposal is eligible iff on validation it beats always-on (finite delta > 0, finite CI), beats cash (own net return > 0), is not degenerate (no multiplier on >= 95% of IN-POSITION bars) and is not vetoed by the critic. The eligible one with the highest validation delta is the single champion; only it plus the competitors (simple rule, LightGBM) go to the frozen test. No champion -> `INCONCLUSIVE`, and `verdict_basis` tells Lane A's arbiter when the unchanged strategy loses to cash.
- **Timeouts are honest.** Stage timeout, request timeout and request limit; tool calls that finish after their stage ended are logged (status `error`, note `abandoned: ...`) and disclosed. `agent_mode` stays within the Lane C contract (`llm` / `llm_with_fallback` / `deterministic_fallback`).
- **LightGBM is out-of-sample on validation**: fitted on early train, calibrated on late train, band preselected around the calibration base rate.

## Adversarial review

Two independent agents attacked Lane B on 7 Nov. Round 1: 18 findings (17 reproduced). Round 2, after the first real Gemini 4 Argon run: 17 findings (16 reproduced), incl. a claim verifier that accepted almost any number, '95% CI' written 4 times in the Argon report, mixed return conventions in the stand-in ('strategy underperforms always-on'), and no comparison with cash. All critical/high findings of both rounds are fixed with regression tests (68 tests after round 2). Note: with the corrected bootstrap (2000 draws, seeded by spec), the stand-in's 'high volatility' effect on train is borderline (90% CI upper bound just above zero), so the strict deterministic fallback now proposes no gate; we did not retune the synthetic data to change that. Remaining known gaps: no Context/News agent yet, no `get_strategy_health` / `run_bootstrap` tools, no news data, and the default loader in tests is the synthetic stand-in.

Round 3 (7 Nov evening), first full `mode=llm` run on Lane A's real BTCUSDT data with Gemini 4 Argon. All three agents ran with no fallback, and the holdout was not accessed. The verifier made the proposer and the critic retry three times: once for an invented number, and once for real numbers cited from the wrong gate's evidence. The critic found that one gate switched more often than always-on (70 vs 50 on validation), that its validation Sharpe failed the proposal's own falsification test, and that the other gate's validation gain came from lower exposure in a falling market. Both gates were rejected; neither beats cash on validation. Fixed after that run:
- the verifier no longer rejects numbers the agents were given (`20` in the instructions, `24`/`72` in `btc-trend-24-72-demo`);
- numbers glued to `h`/`d` (`73h`) are now checked;
- agents are told to round to 3–4 significant digits;
- default timeouts are now 180 s per request and 400 s per stage (Argon's critic hit the old 90 s);
- Lane A's new `momentum_7d`, `atr_14` and `price_drawdown` are allowlisted, and only where the loader reports coverage.

Lane A meanwhile fixed the four contract gaps Lane B reported: compounded cost rows (`switching` is 0 for the unchanged strategy), in-position `allocation_mix` with `n_decisions`/`n_in_position`, a bootstrap seeded by the spec body with 2000 draws, and LightGBM calibrated on late train with its seed and model hash in `spec()`. On real data that LightGBM sits at 0.5 on 99% of in-position validation bars, and Lane B flags it as degenerate.

## Run on Lane A

The default loader is still `fixtures/lane_a_stub.py`, so `tests/test_lane_b.py` does not need the Binance snapshot.

```bash
python3 scripts/run_investigation.py --lane-a --fallback
python3 scripts/run_investigation.py --lane-a --fallback --experiment-id synthetic-btcusdt-1h-v1
python3 scripts/run_investigation.py --lane-a --fallback --frozen
KOK_AGENT_MODEL=google:gemini-4-argon GEMINI_API_KEY=... python3 scripts/run_investigation.py --lane-a   # LLM agents on real data
```

`load_for_lane_b` returns train and validation metrics only. `GateRunner.evaluate` refuses `test`. `--frozen` is the one sealed look, and only for the champion the arbiter accepted. The simple-rule competitor is Lane A's own rule when the loader provides `runner.rule_spec` (flat when the condition fails). The arbiter scores it directly, so the fixed momentum threshold of `0` does not have to sit on the agent quantile grid. Lane A's train-selected regime filter (`runner.regime_spec`) is a third competitor. Each agent gate's reasons show its validation delta against that filter, and the verdict basis states the filter's own result. Like the simple rule, the filter is a reference and not a veto, because the selection rule was registered before any run.

Walk-forward: every agent gate and competitor is also scored with Lane A's `GateRunner.evaluate_folds`. It uses the same three expanding train folds and the same 2-bar embargo as Lane A's LightGBM walk-forward. Each fold is logged in the trial log (note `walk-forward fold k`, split `train`) and stored as evidence the critic can cite. The candidate reasons show "beats always-on on k/3". The fallback critic flags a gate that wins on fewer than half the folds. Thresholds come from quantiles of the whole train window, so the folds are a stability check over train sub-periods, not unseen data, and they do not change the pre-registered selection. The fitted LightGBM has seen all of train (fit plus calibration), so it is not re-scored on the folds. Its line uses Lane A's own walk-forward, which refits the model before each fold (on real data: 0/3).

## Run

```bash
pip install "pydantic-ai-slim[google]" lightgbm scikit-learn pandas numpy pytest
python3 -m pytest -q tests/test_lane_b.py          # 83 guardrail + regression tests
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
