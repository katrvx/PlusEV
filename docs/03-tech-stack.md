# 03 · Tech stack

Every library below was checked on 7 Nov 2026 for: currently maintained, licence compatible with a public hackathon repo, and actually the best tool for the job rather than the most familiar one. "Why" is the important column.

## Core

| Layer | Library | Version | Why | Licence |
|---|---|---|---|---|
| Package manager | **uv** | latest | Resolves and installs the whole env in seconds; lockfile; `uv run` means nobody fights venvs at 3 am. | MIT |
| Python | **3.12** | | Required by several libs below; fast enough; `vectorbt` supports 3.11–3.14. | |
| Dataframes | **Polars** | ≥1.x | Lazy, multi-threaded, 10–50× pandas on our joins (trades × regime bars). Convert to pandas only at library boundaries. | MIT |
| Storage | **DuckDB** | ≥1.x | The tagged-trade table *is* the product; DuckDB gives us SQL over Parquet in-process with zero setup. Both views are queries. | MIT |
| Schemas | **Pydantic v2** | | Every LLM output is a typed schema; every judge output is a typed schema. Validation is the boundary between LLM and code. | MIT |

## Statistics and sequential testing

| Library | Version | Why | Licence |
|---|---|---|---|
| **ville** | 0.1.0 (Oct 2026) | Anytime-valid inference in Python: `BettingTest`, `MSPRT`, confidence sequences (`EmpiricalBernsteinCS`, `BettingCS`), and `evalues.ebh` for e-BH multiple testing. This is the "how many more trades until we know" and the retirement detector. Three weeks old and single-maintainer, so we keep a 60-line fallback e-process in `judge/sequential.py`. | BSD-3 |
| **expectation** | 0.6.1 (Sep 2026) | Alternative: Rust-backed, 300k parallel e-processes, e-BH/e-Holm built in. Only if we need the parallel engine for the swarm's hypothesis set. GPL-3, so only as an optional extra, never a hard dependency. | GPL-3 |
| **arch** | ≥7 | `StationaryBootstrap` and `CircularBlockBootstrap` for serially dependent trade P&L (an iid bootstrap would understate variance). Also GARCH(1,1) for the volatility regime feature. | NCSA |
| **statsmodels** | ≥0.14 | `multipletests` (Benjamini–Hochberg, Holm) for the X-ray's multiple-testing correction; `MarkovRegression` if we want a model-based regime alternative. | BSD-3 |
| **SciPy / NumPy** | | Everything else. | BSD |

## Regime detection

| Library | Version | Why | Licence |
|---|---|---|---|
| **hmmlearn** | ≥0.3 | Gaussian HMM on returns/vol for a *model-based* regime label alongside our rule-based ones. Classic, judges will recognise it. | BSD-3 |
| **ruptures** | ≥1.1 | Offline changepoint detection (PELT, binary segmentation) on the live expectancy series: *when* did performance change. Pairs with the e-detector's *whether*. | BSD-2 |
| **pandas-market-calendars** | | Trading sessions and holidays so "two sessions after FOMC" is computed correctly. | MIT |

## Simulation and backtesting

| Library | Version | Why | Licence |
|---|---|---|---|
| **vectorbt** (open-source) | 1.2 (2026) | `Portfolio.from_signals` simulates thousands of strategy variants in one vectorised call (Numba, optional Rust engine). We use it for the planted-truth simulator: generate signals with a known edge (or none, or edge that dies at *T*), get trades with fees and slippage, output our trade CSV. Also gives drawdown statistics for free. | Apache-2 + Commons Clause (fair-code; fine for us) |
| **quantstats** | | Tear sheets for the deck. One line. | Apache-2 |

Not using: `nautilus_trader` (event-driven, overkill, long setup), `backtrader` (slow, unmaintained), Qlib (great for factor research, wrong shape for this).

## News and events

| Library / source | Why | Licence |
|---|---|---|
| **gdeltdoc** 1.2 | Thin client for the GDELT 2.0 DOC API: headlines by date range, keyword, language, with publication timestamps. Free, no key. | MIT (lib) / GDELT terms (data) |
| **Loughran–McDonald lexicon** | Finance-specific sentiment word lists. Our *baseline* sentiment labeller; the LLM must beat it or we say it doesn't. | Free for research |
| Curated event calendar (JSON) | FOMC, CPI, NFP dates 2015–2026 from federalreserve.gov and bls.gov. Tiny, versioned in repo. | Public domain |

## Agents

| Library | Version | Why | Licence |
|---|---|---|---|
| **google-adk** | 2.x (GA May 2026) | Google's Agent Development Kit. 2.x `Workflow` graphs (and the still-supported `ParallelAgent` / `SequentialAgent` / `LoopAgent`) give us the swarm in ~50 lines: five lens agents in parallel → ledger → judge. Optimised for Gemini, which is the hackathon's main AI sponsor. | Apache-2 |
| **google-genai** | latest | Direct Gemini SDK for the parallel headline labelling (plain structured-output calls, no agent framework needed). Gemini 2.5 Flash for labelling (cheap, fast), Gemini 2.5 Pro for the explainer. | Apache-2 |
| **Pydantic** schemas | | All agent outputs are `output_schema` models. Free-text never crosses into code. | |

Alternative if ADK fights us: **pydantic-ai** (typed agents, model-agnostic). Decide by Saturday 18:00, not later.

## Observability and audit

| Library | Why | Licence |
|---|---|---|
| **structlog** | Structured JSON logs; the audit log is a structlog processor that appends `prev_hash` and `hash` to every event. | MIT/Apache |
| **hashlib (stdlib)** | SHA-256 chain. No blockchain. | |
| **Langfuse** (optional, self-host or free tier) | Traces every LLM call with prompt, output, cost. "Every action logged" for the LLM side. Skip if time is short; structlog already captures inputs/outputs. | MIT |

## App

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** | Typed, async, serves the judge's JSON and the DuckDB queries. |
| Frontend | **React + Vite + TypeScript** | Fast to scaffold; traders expect a trading-app look. |
| Charts | **TradingView lightweight-charts** (price + trade markers + regime bands) and **ECharts** (heatmap, drawdown distribution) | lightweight-charts is what traders already stare at all day; the regime bands over the price chart are the single most convincing visual we have. |
| Styling | **Tailwind** | No design debates. |
| Fallback | **Streamlit** | If the React app isn't rendering by Saturday 22:00, the whole UI becomes one Streamlit page with Plotly. Decide at 22:00, not at 3 am. |

## Dev

| Tool | Why |
|---|---|
| **ruff** | Lint + format, one tool. |
| **pytest + hypothesis** | Property tests for the judge: e.g. "on pure-noise trades the X-ray admits ≤ α of hypotheses" is a test, not a hope. |
| **pre-commit** | Ruff on commit. |
| **GitHub Actions** | `uv sync && pytest` on push. Judges read the repo; a green check is cheap credibility. |

## Install (planned `pyproject.toml` extract)

```toml
[project]
name = "barometer"
requires-python = ">=3.12,<3.15"
dependencies = [
  "polars>=1.0", "duckdb>=1.0", "pydantic>=2.7",
  "numpy", "scipy", "statsmodels>=0.14", "arch>=7",
  "ville>=0.1.0", "hmmlearn>=0.3", "ruptures>=1.1",
  "vectorbt>=1.2", "quantstats", "pandas-market-calendars",
  "gdeltdoc>=1.2", "google-adk>=2.0", "google-genai",
  "structlog", "fastapi", "uvicorn", "yfinance",
]
[project.optional-dependencies]
fast = ["expectation>=0.6"]      # GPL-3, optional
trace = ["langfuse"]
dev = ["ruff", "pytest", "hypothesis", "pre-commit"]
```

## Things that will bite, known in advance

- `vectorbt` 1.x needs Python ≥3.11 and pulls Numba; first import compiles for ~20 s. Fine.
- `ville` is 0.1.0. Pin it. Keep the fallback e-process. Test both give the same stopping times on synthetic data.
- GDELT DOC API rate-limits bursts; pull once into Parquet, never call it from the app.
- Gemini structured output: use `response_schema` with the Pydantic model's JSON schema; validate again with Pydantic on receipt. Trust nothing.
- `hmmlearn` can flip state labels between fits; sort states by mean volatility after fitting.
