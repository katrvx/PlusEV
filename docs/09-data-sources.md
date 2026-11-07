# 09 · Data sources

Track rule: *"Reference every dataset and check its licence."* Some free market data is non-commercial only. This is a hackathon project under MIT; the data stays non-commercial where its licence says so, and the deck says which.

| Dataset | Use | How we get it | Licence / terms | Notes |
|---|---|---|---|---|
| **AgentVerse finance kit** | Real price history; "hidden test mode" | From organisers | Per kit terms | Preferred source. Ask at the mentor desk for the hidden-test protocol; if it fits, we report +EV on it as an extra holdout. |
| **Yahoo Finance via `yfinance`** | Daily OHLCV for 20 US large caps + SPY, 2015–2025 | `yfinance.download` once, cached to Parquet | Yahoo terms: personal/non-commercial use | Adjusted closes for returns; raw for liquidity proxies. |
| **Binance Vision** | Daily/hourly OHLCV for BTC, ETH, SOL, BNB, XRP vs USDT | `data.binance.vision` monthly zips | **CC BY-NC-SA 4.0** (non-commercial, share-alike) | Explicitly flagged non-commercial in the deck. |
| **GDELT 2.0 DOC API** | Headlines with publication timestamps, 2015–2025 | `gdeltdoc` client, pulled once, cached | Free; GDELT terms of use (attribution) | Pull by keyword themes per symbol/market; respect rate limits; never called from the app. |
| **FRED** | Fed funds rate, 10Y yield, VIX (for macro context in the explainer, not as regime features in v1) | `fredapi` with a free key | Public domain (series-dependent; FRED terms) | Optional. |
| **Federal Reserve FOMC calendar** | Decision dates 2015–2026 | Curated JSON in repo from federalreserve.gov | Public domain | |
| **BLS release calendar** | CPI, NFP dates 2015–2026 | Curated JSON from bls.gov | Public domain | |
| **Loughran–McDonald lexicon** | Sentiment baseline | Downloaded once from the authors' site | Free for academic/research use | Attribution in deck. |
| **Synthetic trades (our simulator)** | Planted-truth evaluation | Generated | Ours (MIT) | Labelled synthetic; method in [07](07-evaluation-protocol.md). |
| **Trader-supplied backtest/live CSVs** | Demo only | Our own sample files | Ours | No real financial records, account details or logins, per track rules. |

## Not used, and why

- Polymarket / Kalshi: not needed for this problem.
- Elliptic / PaySim / AMLSim: fraud datasets, wrong problem.
- Paid data (Polygon, Databento): not needed at daily resolution.
- Any intraday tick data: out of scope; our regimes are daily/hourly.

## Storage

`data/raw/<source>/…` (as pulled, with a `MANIFEST.json` recording URL, pull time, licence) → `data/parquet/<table>.parquet`. The manifest is what the deck's data slide is built from.

## Rules we follow

- No real accounts, keys or logins in the repo. `.env` is git-ignored; a `.env.example` lists variable names only.
- Synthetic data is labelled synthetic everywhere it appears.
- Backtests are never presented as real-world performance.
- Paper trading only.
