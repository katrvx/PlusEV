# 04 · Regime engine

The regime engine turns every bar into a small vector of **conditions that were knowable at that bar's open**, then tags every trade with the vector at its entry. Everything in this doc is `[code]` except the sentiment score, which is `[LLM]` with a code baseline.

## Rule 0: no look-ahead, enforced structurally

Every regime feature at bar *t* may use only data with timestamp **< open(t)**. We enforce this with a single function `features_as_of(ts)` that takes a cutoff and raises if asked for anything later. Tests in `tests/test_no_lookahead.py` shift the cutoff and assert the feature is unchanged. Headlines use their GDELT publication timestamp, not the date they're "about".

This is not pedantry. Regime analysis is the most overfit thing in retail trading, and look-ahead in the regime label is the most common way it goes wrong. Judges will ask.

## Regime features

All computed per symbol per bar (daily by default; hourly where data allows). Each has a continuous value and a bucketed label; hypotheses are tested on buckets.

| Feature | Definition (as of bar open) | Buckets | Why it matters |
|---|---|---|---|
| **Realised vol** | 20-bar std of log returns, annualised; plus GARCH(1,1) one-step forecast from `arch` | low / mid / high by rolling 1-year terciles | Mean-reversion loves low vol; trend-following loves high. The first thing any quant would check. |
| **Vol-of-vol / vol shock** | ratio of 5-bar to 60-bar realised vol | calm / rising / shock (>2×) | "The week it blew up" detector. |
| **Trend** | sign and magnitude of 50-bar vs 200-bar MA gap; ADX(14) | up / down / chop | Chop kills breakout bots; trend kills mean reversion. |
| **Liquidity** | 20-bar median dollar volume; relative spread proxy (high−low)/close | thin / normal / deep (terciles) | Where slippage lives. Explains the "execution" part of the decomposition. |
| **Event window** | days to nearest scheduled event (FOMC, CPI, NFP; earnings for the symbol) | pre-event (−2..−1) / event / post-event (+1..+2) / none | The single most interpretable regime. "Loses around rate decisions" is a sentence a trader can act on. |
| **Session / weekday** | weekday; for crypto: Asia / Europe / US session | categorical | Cheap, often real (weekend crypto liquidity). |
| **HMM state** | 2–3 state Gaussian HMM on (return, vol) fitted on the training window only; states sorted by vol | state 0/1/2 | A model-based label alongside the rule-based ones; judges recognise it. |
| **News sentiment** | LLM score on anonymised headlines published before open; lexicon baseline alongside | negative / neutral / positive by terciles | The one feature only an agent can produce. Must beat the lexicon or we say so. |
| **News volume** | count of matching headlines in prior 24 h vs 30-day mean | quiet / normal / loud | "Something happened" without needing to know what. |

Bucket boundaries (terciles) are computed on the **training window only** and frozen; the holdout uses the frozen boundaries.

## Sentiment labelling `[LLM]`

Input per day: up to 30 headlines matching the symbol/market themes, published in the 24 h before that bar's open.

**Anonymisation before the LLM sees anything:**
- Dates and years removed or replaced with `[DATE]`.
- Tickers and company names replaced with `[ASSET]`, `[COMPANY_1]`, …
- Named people → `[PERSON]`. Central banks kept as `[CENTRAL_BANK]`.
- Numbers kept (a 75 bp hike is information, not identification).

Output schema (Pydantic, enforced):

```python
class DaySentiment(BaseModel):
    score: float = Field(ge=-1, le=1)          # −1 very negative … +1 very positive
    confidence: float = Field(ge=0, le=1)
    event_type: Literal["rates","inflation","earnings","geopolitics","regulation","crypto_specific","macro_data","none"]
    rationale: str = Field(max_length=200)     # for the audit log, never used by the judge
```

Run in parallel (Gemini 2.5 Flash, `google-genai`, 20 workers). Cached to Parquet keyed by (day, symbol, headline-set hash). Never called from the live app path.

**Baseline:** Loughran–McDonald positive/negative word ratio on the same headlines. Reported side by side.

**Memorisation guard:** a random 10% of days are *also* labelled un-anonymised. If LLM sentiment predicts next-day returns markedly better with dates visible than without, the LLM is recalling, not reading, and the sentiment feature is demoted to "replay only" in the report. See [06](06-agents-and-swarm.md).

## Tagging trades

```sql
-- DuckDB, conceptually
CREATE TABLE tagged AS
SELECT t.*, r.*
FROM trades t
ASOF JOIN regimes r
  ON t.symbol = r.symbol AND t.entry_ts >= r.bar_open
```

`ASOF JOIN` picks the latest regime bar at or before entry. DuckDB does this natively, which is the main reason it's in the stack.

## Pre-registration of hypotheses

A hypothesis is a tuple `(feature, bucket, direction)`, e.g. `("event_window", "post-event", "underperform")`. The swarm proposes them from the strategy description **before any P&L is visible**. Canonical form is hashed; duplicates are refused and counted. The budget is fixed per strategy (default 40 slots). The ledger records every proposal, accepted or refused, with the proposing agent and timestamp. The judge tests **only** registered hypotheses, and reports the total count tried. Details in [05](05-judge-and-stats.md) and [06](06-agents-and-swarm.md).

A default panel of 12 hypotheses (one per feature × plausible direction) is always registered first, so a strategy with a vague description still gets a complete X-ray.

## What we are not doing

- No sub-daily sentiment. GDELT updates every 15 minutes but our strategies are daily/hourly; finer is noise.
- No "AI finds the regime" on P&L. Regimes are defined from market data and the description, never from where the bot happened to make money. That is the whole point.
- No regime *prediction*. We label the regime the bot is in now; we do not forecast tomorrow's. (The forum thread where someone tried to predict good days is the cautionary tale.)
