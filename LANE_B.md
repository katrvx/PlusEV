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

Two independent agents attacked Lane B on 7 Nov. Round 1: 18 findings (17 reproduced). Round 2, after the first real Gemini 4 Argon run: 17 findings (16 reproduced), incl. a claim verifier that accepted almost any number, '95% CI' written 4 times in the Argon report, mixed return conventions in the stand-in ('strategy underperforms always-on'), and no comparison with cash. All critical/high findings of both rounds are fixed with regression tests (68 tests after round 2). Note: with the corrected bootstrap (2000 draws, seeded by spec), the stand-in's 'high volatility' effect on train is borderline (90% CI upper bound just above zero), so the strict deterministic fallback now proposes no gate; we did not retune the synthetic data to change that. Remaining known gaps: no Context/News agent yet, no `run_bootstrap` tool (CIs come from Lane A), no news data, and the default loader in tests is the synthetic stand-in.

Round 3 (7 Nov evening) started from the first full `mode=llm` runs on Lane A's real BTCUSDT data with Gemini 4 Argon. In the first one (19:24, not committed), all three agents ran with no fallback, and the holdout was not accessed. The verifier made the proposer and the critic retry three times: once for an invented number, and once for real numbers cited from the wrong gate's evidence. The critic found that one gate switched more often than always-on (70 vs 50 on validation), that its validation Sharpe failed the proposal's own falsification test, and that the other gate's validation gain came from lower exposure in a falling market. Both gates were rejected; neither beats cash on validation. Fixed after that run:
- the verifier no longer rejects numbers the agents were given (`20` in the instructions, `24`/`72` in `btc-trend-24-72-demo`);
- numbers glued to `h`/`d` (`73h`) are now checked;
- agents are told to round to 3–4 significant digits;
- default timeouts are now 180 s per request and 400 s per stage (Argon's critic hit the old 90 s);
- Lane A's new `momentum_7d`, `atr_14` and `price_drawdown` are allowlisted, and only where the loader reports coverage.

Lane A meanwhile fixed the four contract gaps Lane B reported: compounded cost rows (`switching` is 0 for the unchanged strategy), in-position `allocation_mix` with `n_decisions`/`n_in_position`, a bootstrap seeded by the spec body with 2000 draws, and LightGBM calibrated on late train with its seed and model hash in `spec()`. With the old 0.45/0.55 cut that LightGBM sat at 0.5 on 99% of in-position validation bars, and Lane B flagged it as degenerate. Lane A then switched to a band of the train-tail base rate ± 2 points. It is no longer degenerate, but it loses: −17.7% vs always-on on validation and 0/3 on Lane A's refit walk-forward.

The committed artifact `experiments/investigation_argon_lane_a.json` is the final Argon run (8 Nov, morning), on the code with walk-forward folds and the strategy-health check. All three agents ran on Argon (`mode=llm`), and the holdout was not accessed. The proposer submitted three gates: `fear_greed > 53` at full/zero, the same at full/half, and low volatility at full/half. The critic rejected all three. It used both new tools on its own. From `strategy_health` it cited the sentiment shift (50.67% fear on train to 99.31% on validation, total variation 0.4864), which leaves the Fear & Greed gates off or at half size 99% of the time. From the walk-forward folds it showed that the shift had already started in the last train fold (gate off 90.69% of the time). It also found that each gate fails its own falsification test (validation Sharpe below always-on). The volatility gate switched more often than always-on (70 vs 50). No gate beats cash, so the verdict is INCONCLUSIVE. The verifier rejected three outputs. One was a correct catch (`twenty` written as a word). The other two were false positives that are now fixed: `14` in '14-day blocks', which the evidence only stated as 336 bars, and the 20-trade threshold written in a form the verifier did not recognise.

A third independent review (round 3) then attacked everything above: 13 findings, all reproduced. Critical: after the walk-forward change, rule (c) (no degenerate gate) only ran when fold results existed, so a degenerate gate approved by an LLM critic could reach the sealed test on a runner without folds. Fixed, with a regression test on the stand-in runner. Also fixed:
- verifier leaks: `.9876`, a Unicode minus, numbers like `0.3` passing for 0.251, `2e2 trades`, a bare `20`, written zeros, and free numbers drawn from upload ids;
- real-data runs were written under the synthetic fixture's file name;
- the regime filter posed as a competitor when it had selected no buckets (it is always-on, and is now reported as such);
- failed folds were described as missing folds;
- trial records now carry a structured `fold`;
- Lane A's notes, which quote the sealed-test verdict, are dropped from what agents can see.

## Bad luck vs broken (`health.py`)

Spec section 8: a poor result alone is not proof that a strategy broke. Code, not an agent, cuts the unchanged strategy's validation period into 14-day blocks. It compares each block with Lane A's train-only 14-day range (5th to 95th percentile of block-bootstrapped train paths). About 5% of blocks should fall below that range by chance. If more do (one-sided binomial p < 0.05), the result is `outside_training_range`; otherwise it is `within_training_range`. It also checks which assumption changed between train and validation: exposure, turnover per bar, cost per bar, bar volatility (ratio outside 2/3–3/2), and how often each regime occurs (total variation ≥ 0.25). The thresholds are fixed in the module. Because the check reads validation, only the critic can call it (`strategy_health` tool) and it appears in the report (`strategy_health`, plus a line in `verdict_basis`). The fallback critic notes when the regime behind a gate's feature shifted.

On real data: 10 of 10 validation blocks fall inside the train range [−9.1%, +10.1%]. The −7.1% validation loss is therefore not by itself evidence that the strategy broke. One assumption did change: sentiment went from about 51% "fear" bars on train to 99% on validation. That is exactly why the agent's Fear & Greed gate collapsed.

## Two strategies on real data

Both of Lane A's demo strategies on the same BTCUSDT 1h snapshot (validation results; the test stays sealed):

| | `btc-trend-24-72-demo` | `btc-meanrev-48-demo` |
|---|---|---|
| Train net (gross) | +5.1% (+27.8%) | −22.0% (+10.4%): costs eat the edge |
| Validation always-on | −7.1%, 90% CI spans zero | −40.3%, 90% CI entirely below zero |
| Bad luck vs broken | `within_training_range`: 10/10 two-week blocks inside the train range. Sentiment shifted | `outside_training_range`: 3/10 blocks below the range, more than chance. Cost per bar and sentiment shifted |
| Agent gates (Argon) | 3 proposed, all vetoed by the critic. The Fear & Greed gates are off or at half size 99% of validation after the sentiment shift, and each fails its own falsification test | 3 proposed, all approved by the critic. The best, high volatility plus a drawdown, is +14.8% vs always-on (CI above zero), wins 3/3 train folds and beats the regime filter by 4.3%. It still nets −25.5%, so the code rejects every gate for losing to cash |
| Lane B verdict | INCONCLUSIVE: looks like bad luck plus a regime change | INCONCLUSIVE, with a note to Lane A's arbiter that the strategy loses to cash. A gate that loses less does not make it profitable: a kill candidate |

Reports (both Gemini 4 Argon, `mode=llm`, no agent failures, holdout not accessed): `experiments/investigation_argon_lane_a.json` and `experiments/investigation_argon_meanrev.json`.

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
python3 -m pytest -q tests/test_lane_b.py          # 111 guardrail + regression tests
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
