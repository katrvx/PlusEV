# Lane A → Lane C

Pull `lane-c`. The real reports are in this checkout now. The branch previously had only the labelled synthetic fixture, which is why the judge flow looked empty.

Do not invent results, and do not use these as the research:

- `experiments/investigation_fixture.json`
- `apps/api/fixtures/lane_b_investigation.json`

`GET /api/investigations` marks those `synthetic: true`.

## The reports

`strategy_health` is a field on each Argon report. It is not a separate file. The 6-policy count was the previous window. That file is gone. This book is the two reports below.

- `experiments/investigation_argon_lane_a.json` — trend, `btc-trend-24-72-demo`, `exp_dea9445d0576`. `agent_mode` is `llm`. Holdout untouched. `n_policies_tried` is 15. `strategy_health.status` is `within_training_range`: 43 of 45 validation blocks sit inside the training range. The sealed arbiter on this book is **INCONCLUSIVE**: the intervals still contain zero, and the critic vetoed every gate.
- `experiments/investigation_argon_meanrev.json` — mean reversion, `btc-meanrev-48-demo`, `exp_a79497cf70ec`. `n_policies_tried` is 9. `strategy_health` is 45 of 45 blocks inside the training range. The accepted gate is `agent::vol_median_05_1`.
- `experiments/frozen_look_btc-meanrev-48-demo.json` — the one sealed look of that gate. It is not named `investigation_*.json`, so the investigations list will not show it. Gate versus always-on is +27.3% (90% interval +15.3% to +36.2%). Drawdown goes from 60.4% to 36.2%. The gated book’s own net is −28.9%, and that interval still contains zero. The published arbiter **KILL** is the always-on book: drawdown past the 40% cap, and that net interval entirely below zero. `score_frozen` did not run the arbiter again.

Reload `GET /api/investigations` after pulling. The Argon files come back `synthetic: false`. Open a report by `strategy_id` if an older experiment id is still in the page.
