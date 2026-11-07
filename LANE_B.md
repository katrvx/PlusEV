# Lane B — Agents / Context

Owner: Kate. Implements AGENTS.md Lane B against the project spec. Runs today without Lane A, using a clearly-labelled synthetic stand-in in `fixtures/lane_a_stub.py` that implements the same interface Lane A promised.

## Output interface

```python
from packages.research_agents.investigate import investigate
report = investigate(experiment_id)        # -> InvestigationReport (pydantic), JSON via report.model_dump_json()
```

`InvestigationReport` contains: `verdict` (`candidate_for_frozen_test` or `INCONCLUSIVE`), `champion_policy_id` (at most ONE agent policy), ranked hypotheses with evidence ids, gate proposals, critiques, the full trial log (every attempt incl. refused ones, keyed by spec hash), candidates with validation delta vs always-on AND vs the simple rule, CI and allocation mix, test requests for Lane A, limitations, every piece of evidence (raw tool output), `agent_failures`, `n_distinct_agent_policies`, `n_policies_tried`, `holdout_accessed`, and `agent_mode` (`llm`, `llm_with_fallback`, `deterministic_fallback`).

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
- **Claims are checked, not just ids.** Numbers in hypotheses/summary must match the cited tool output; regime conditions must be buckets that exist in the cited rows; critiques must cover exactly the real proposals and cite each gate's own evaluation.
- **Results keyed by spec hash**, so two proposals with the same name can never share a result; duplicate ids are rejected.
- **Robust to LLM failure.** Bad tool arguments become retries; any LLM stage failure falls back to the deterministic agent and is listed in `agent_failures`.
- **Missing data is conservative**: a row with a missing gate feature gets min(allocation_when_true, allocation_when_false).
- **No strategy changes, no code execution, no orders.** Gates output multipliers only.
- **News is point-in-time.** Visible only if `first_seen_at <= decision cutoff`; coverage reported; never used in a gate unless coverage ≥ 90%.
- **The arbiter is code.** Pre-registered rule: among agent proposals with validation delta > 0, critic approval and a non-degenerate allocation mix (no multiplier on >= 95% of decisions), the ONE with the highest validation delta is the champion. Only it plus the competitors (simple rule, LightGBM) go to the single frozen test. No champion -> `INCONCLUSIVE`. LLM confidence cannot override it.
- **LightGBM is out-of-sample on validation**: fitted on early train, calibrated on late train, band preselected around the calibration base rate.

## Adversarial review

An independent agent attacked Lane B on 7 Nov (18 findings, 17 reproduced). All critical and high findings are fixed and each has a regression test (38 tests total). Remaining known gaps: no Context/News agent yet, no `get_strategy_health` / `run_bootstrap` tools, no news data, the LLM path has only been exercised with scripted models, and the Lane A stand-in is synthetic.

## Run

```bash
pip install "pydantic-ai-slim[google]" lightgbm scikit-learn pandas numpy pytest
python3 -m pytest -q tests/test_lane_b.py          # 38 guardrail + regression tests
python3 scripts/run_investigation.py --fallback     # deterministic agents
KOK_AGENT_MODEL=google:gemini-2.5-flash GEMINI_API_KEY=... python3 scripts/run_investigation.py   # LLM agents
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
