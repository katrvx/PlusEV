# 06 · Agents and swarm

## The one rule

**Agents propose, label and explain. The frozen judge decides. No LLM output is ever a number in a verdict.**

Why this is the thesis and not a cop-out: three papers from the last eight weeks (full citations in [12](12-references.md)) tested exactly the alternative.

- *Are LLM Research Agents Reliable Judges of Predictability?* (Nov 2026): in worlds with **no signal**, agents given the verdict claimed predictability 34–44% of the time (Opus 5.5, GPT-6.1, Qwen3-32B). Calibration slope 0.36. One optimistic sentence in the brief raised false claims from 15% to 32%. Recommendation: neutral brief, decision rule fixed outside the agent, sealed holdout.
- *Propose, Don't Judge* (Sep 2026): when the proposer could see verdicts and resubmit, a leaky judge admitted 2.6–11× more false factors. The LLM's most valuable contribution was **writing diagnostic probes**, not judging.
- *Hard to Fool* (Nov 2026): LLM emits declarative JSON, trusted code decides; most hypotheses fail honestly.

We build what those papers recommend, for a different problem.

## Three jobs for agents

### 1. Headline labelling (parallel, no agent framework)

Plain `google-genai` structured-output calls, Gemini 2.5 Flash, 20 workers, cached to Parquet. Schema in [04](04-regime-engine.md). Anonymised input. This is throughput work; an agent framework would be ceremony.

### 2. Hypothesis swarm (Google ADK)

Five **lens agents** run in parallel. Each receives the **same neutral brief**: the strategy description written by the trader, the list of available regime features and buckets, and nothing else. No P&L, no equity curve, no dates.

| Agent | Lens | Example proposal |
|---|---|---|
| `vol_lens` | volatility, vol shocks | "Mean-reversion on 5-min bars should underperform when `vol_shock` = shock" |
| `macro_lens` | scheduled events, rates, inflation | "Should underperform in `event_window` = post-event for FOMC" |
| `sentiment_lens` | news tone and volume | "Should underperform when `news_volume` = loud and `sentiment` = negative" |
| `liquidity_lens` | depth, spread, session | "Should underperform in `liquidity` = thin; and in Asia session for crypto" |
| `devils_advocate` | "where should this *fail* given how it's built?" | "Trend-following with a 50-bar lookback should bleed in `trend` = chop" |

Output schema per agent (Pydantic, enforced by ADK `output_schema`):

```python
class Hypothesis(BaseModel):
    feature: Literal["realised_vol","vol_shock","trend","liquidity","event_window",
                     "session","hmm_state","sentiment","news_volume"]
    bucket: str
    direction: Literal["underperform","outperform"]
    rationale: str = Field(max_length=240)   # logged, never used by judge

class HypothesisSet(BaseModel):
    hypotheses: list[Hypothesis] = Field(max_length=8)
```

ADK 2.x `Workflow`: `[vol_lens ‖ macro_lens ‖ sentiment_lens ‖ liquidity_lens ‖ devils_advocate] → ledger → judge`. The `ParallelAgent` / `SequentialAgent` forms still work in 2.x if the graph API costs time.

**Pre-registration ledger `[code]`** sits between swarm and judge:
- canonicalise `(feature, bucket, direction)`, hash, refuse duplicates (counted);
- enforce the slot budget (default 40 per strategy, including the 12-hypothesis default panel);
- append every proposal and refusal to the audit log with agent id;
- emit the final registered set and the **total count tried** to the judge.

The judge tests only registered hypotheses and corrects for the count. The deck reports the chain: *"5 agents proposed 31 hypotheses (4 duplicates refused), 9 survived BH on training, 6 confirmed on holdout."*

**What the swarm buys versus one agent:** diversity of hypotheses, and a story. The multiple-testing correction makes the diversity safe. Build the single-agent path first; the swarm is a loop around it ([10](10-build-plan.md)).

### 3. Explainer

Gemini 2.5 Pro receives the judge's JSON and the strategy description and writes the verdict in plain language for the UI.

**Hard constraint, enforced in code:** every number in the explanation must appear in the judge's JSON (regex extraction, numeric match with tolerance). If the explainer invents a number, the output is rejected and regenerated with the violation shown. After two failures the UI shows the judge's table without prose.

The explainer may: restate numbers, order them by importance, name the regime in words, recommend *keep / reduce / stop / wait N trades* **from the judge's own recommendation field**. It may not: change the recommendation, add a probability, soften a "stop".

### 4. (Live tab) Competing explanations

When Kill or Keep finds a gap, lens agents may each propose *one* explanation (`execution | signal | regime:<bucket>`). The judge scores them against the decomposition in [05 B3](05-judge-and-stats.md); the explainer reports which explanation the data supports. Agents argue, data decides.

## Memorisation guard

An LLM labelling 2022 headlines knows what happened in 2022. If sentiment "predicts" returns, it may be recall, not reading.

Protocol:
1. All labelling uses anonymised headlines ([04](04-regime-engine.md)).
2. A random 10% of days are *also* labelled with dates and names visible.
3. Compute the information coefficient (rank correlation of sentiment with next-day return) for both versions on the same days.
4. If IC(visible) − IC(anonymised) exceeds its bootstrap 90% CI, the sentiment feature is flagged **"replay-contaminated"** and demoted: it stays in the X-ray tables with the flag, and is excluded from the filter test in [05 A4](05-judge-and-stats.md).
5. The lexicon baseline is always shown beside the LLM score.

Reported in the deck whatever the result. Finding contamination is a result.

## Framing neutrality

Per the Nov 2026 paper: the brief to the lens agents contains no prior claims ("this strategy has worked well", "we expect it to fail in high vol"). The trader's strategy description is passed through a **neutraliser** step that strips performance claims (regex + one Flash call that returns only the mechanism description). The stripped text is logged.

## Prompt sketches

**Lens agent (system):**
> You are one of several analysts. You will read a description of a trading strategy's mechanism. You do not know how it performed. Propose up to 8 hypotheses, in the given schema, about market conditions in which this mechanism should under- or outperform, based only on how it works. Prefer specific, testable conditions. Do not propose conditions you cannot map to the listed features.

**Explainer (system):**
> You will receive a JSON verdict produced by a statistical engine. Write the verdict for a trader in under 150 words. Use only numbers present in the JSON. Do not add probabilities or recommendations not present in the JSON. Name the regime in plain words. State the recommendation exactly as given.

## Costs

Labelling ~2,500 days × 30 headlines on Flash ≈ cents. Swarm per strategy ≈ 5 calls. Explainer ≈ 1 call per verdict. Hackathon credits are not a constraint; rate limits are, hence caching.
