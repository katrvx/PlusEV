# Lane B against the original idea

Checked 7 Nov 2026 against `KEEP_OR_KILL_PROJECT_SPEC.md` section 9, `KEEP_OR_KILL_AGENTS.md` Lane B, and `packages/research_agents` on `main` at `91ceb32`.

Lane B is still the original product. It investigates an unchanged strategy, cites tool output, and refuses the holdout. It does not decide Keep or Kill. That decision stays with Lane A's arbiter. That split is recorded in [`INTEGRATION_DECISIONS.md`](INTEGRATION_DECISIONS.md).

## Still the idea

- Gates are allocation multipliers. Agents cannot run uploaded code or edit the signal.
- Diagnostic, critic, and gate proposer are built. A verifier rejects numbers that are not in the cited tool output. A fallback runs when the model fails.
- Tools refuse the test split. One champion gets one sealed look. The critic sees validation only through the trial log.

## Where it moved

| Original idea | What Lane B does now |
|---|---|
| The decision is keep, activate conditionally, reduce, combine, monitor, kill, or not proven. | Lane B reports `candidate_for_frozen_test` or `INCONCLUSIVE`. Lane A's arbiter stores `MODIFY` and `RESTRICT` for activate-conditionally and reduce. The screen uses the spec words. |
| An interval that still contains zero is not a decision. | A positive validation delta whose 90% interval includes zero can still be the agent champion. The code says the frozen test decides. Lane A may then abstain. |
| Compare the overlay with always-on, the simple rule, and cash. | Cash is a veto: validation net return must be above zero. A gate that only loses less than the original strategy, while still losing to cash, cannot be the champion. |
| Challenge the agent gate on the same walk-forward splits as the baselines. | Done after this note (Lane B `2ad3da0`): every agent gate and competitor is also scored with `GateRunner.evaluate_folds`, the critic reads the folds in the trial log, and LightGBM uses Lane A's refit walk-forward. Thresholds come from all of train, so folds are a stability check, not unseen data. |
| News and sentiment, with a context agent, and no causal claim from a headline. | The context agent reads Fear & Greed around the best and worst train weeks and rejects causal wording. News stays omitted: coverage is 0 and there is no first-seen archive. The spec says to cut news before cutting execution. |
| Tools include strategy health and a bootstrap. | Strategy health is built (`health.py`, critic tool `strategy_health`, uses `train_predictive_range`). A separate bootstrap tool is not; CIs come from Lane A. |
| Combine two strategies when they complement each other. | Not in this lane. One investigation is one book, same as Lane A. |

## The champion rule, as coded

An agent gate reaches the single sealed look only if its validation delta versus always-on is above zero, its own net return is above zero, no multiplier covers 95% or more of in-position bars, and the critic approves it. Among those, the largest validation delta wins. A confidence interval that still covers zero is noted and does not block the look.

Source: `packages/research_agents/investigate.py`, the pre-registered selection block.
