# 08 · Risk controls and audit log

Rubric: *"Limits enforced in code, every action logged, one control shown live."* (15%) And from the brief: *"Keep a human in the loop for anything that moves money or affects a person."*

## Paper only

+EV never connects to an exchange or broker with live credentials. The "live" tab consumes a trade CSV, a paper-trading feed, or a replay. There is no order-sending code path in the repository. This is a rule, not a setting.

## Controls, all in `plusev/risk/controls.py`

| Control | Rule | Enforced where | Logged |
|---|---|---|---|
| **Size cap** | Recommended position size ≤ `min(half-Kelly on the lower bound of live expectancy, backtest average size)`. Half-Kelly: f = ½ · μ_lo / σ², with μ_lo the lower 80% confidence-sequence bound from `ville`. | Judge output; the UI cannot display a larger size than the control returns. | yes |
| **Drawdown pause** | If live drawdown exceeds the backtest's 99th-percentile bootstrap drawdown, status becomes `PAUSED`. Resumption requires a human click that writes a signed reason to the log. | `controls.py`; UI button disabled until reason entered. | yes |
| **No doubling down** | A size increase is refused if the last 3 trades were losses or the drawdown percentile > 90. The refusal is logged with the attempted size. | `controls.py` | yes |
| **Cooling-off** | A manual override (stop/resume/resize) cannot be reversed within 4 hours. (The practitioner write-up that cut interventions from 11 to 1 used exactly this.) | `controls.py` | yes |
| **Sealed holdout** | Holdout opens once per strategy, after a receipt. Second attempt raises. | `judge/holdout.py` | yes |
| **Hypothesis budget** | 40 slots per strategy; refusals counted. | `swarm/ledger.py` | yes |
| **Explainer number check** | Prose containing numbers not in the judge JSON is rejected. | `explain/check.py` | yes |

## The control shown live (demo)

The trader, mid-drawdown, tries to double size "to make it back faster". The UI shows: *"Refused: 3 consecutive losses and drawdown at the 94th percentile. Rule: no size increase under these conditions. Logged."* Then they try to stop the bot; +EV shows the verdict (within expectation, 78% alive, 35 trades to a 90% answer) and the **override ledger** entry that will be scored later. They can still stop it. The human decides; the system makes the decision honest and recorded.

## Override Ledger

Every manual action: `{ts, strategy_id, action, size_before, size_after, judge_verdict_at_time, reason}`. After the fact, the ledger scores each override: P&L of the path taken vs. the path +EV recommended, over the next *k* trades. The UI shows the running tally: *"Your overrides: 7. Net effect vs. recommendation: −2.1%."* This is the feature the practitioner team built by hand in a spreadsheet.

## Audit log

Append-only JSONL, `audit/log.jsonl`. Each event:

```json
{"seq": 1042, "ts": "...", "kind": "judge.xray", "strategy_id": "...", "payload": {...},
 "prev_hash": "sha256:...", "hash": "sha256:..."}
```

`hash = sha256(prev_hash + canonical_json(event_without_hash))`. A `verify` command walks the chain. Kinds: `data.pull`, `regime.label`, `sentiment.label`, `swarm.propose`, `ledger.accept`, `ledger.refuse`, `judge.xray`, `holdout.receipt`, `holdout.open`, `judge.killorkeep`, `explain.ok`, `explain.reject`, `risk.refuse`, `risk.pause`, `override`, `override.score`.

Every verdict in the UI links to its log entries, so "any decision traces from raw data to output" is literally clickable.

## What this does not do

- It does not stop a trader who insists. It records them.
- It does not size for the trader's whole portfolio; the cap is per strategy.
- It does not protect against the future being unlike the past. Nothing does; that's why the human is in the loop.
