# 12 · References

## Papers that shaped the design

- **R&D-Agent-Quant: A Multi-Agent Framework for Data-Centric Factors and Model Joint Optimization.** Li et al., NeurIPS 2025. https://arxiv.org/pdf/2505.15155 — the LLM-in-the-loop quant research baseline; limitations: internal knowledge only, no regime adaptation.
- **Propose, Don't Judge: An Anytime-Valid Referee for LLM Agents That Mine Investment Factors.** Sept 2026. https://arxiv.org/pdf/2609.27051 — frozen referee with betting e-processes and online e-BH; leaky judges admit 2.6–11× more false factors; LLM's best contribution is diagnostic probes.
- **Hard to Fool: A Bounded LLM Research Loop for Quantitative Finance, and What Two Dozen Campaigns Found.** Nov 2026. https://arxiv.org/html/2611.06607 — declarative proposals, staged evidence, sealed holdout with receipt, gates not scores, hash-chained ledger.
- **Are LLM Research Agents Reliable Judges of Predictability? Evidence from Planted-Signal Worlds.** Nov 2026. https://arxiv.org/html/2611.04070 — 34–44% false claims in no-signal worlds; calibration slope 0.36; framing sensitivity; memorisation of published factor returns; recommendations we follow.
- **Agentic Quantitative Trading: A Survey of Workflows, Systems, and Evaluation.** Aug 2026. https://arxiv.org/pdf/2608.31041 — only 2 of 20 systems carry signals through risk; nobody separates regime shift from lost predictive ability.
- **Implementation Risk in Portfolio Backtesting: A Previously Unquantified Source of Error.** Mar 2026. https://arxiv.org/pdf/2603.20319
- **AlphaAgent: LLM-Driven Alpha Mining with Regularized Exploration to Counteract Alpha Decay.** KDD 2025. https://arxiv.org/pdf/2502.16789
- **Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets.** AFT 2025. https://alphaxiv.org/overview/2508.03474v1 — considered and not pursued.

## Statistical methods

- Ville, J. (1939). Étude critique de la notion de collectif. — Ville's inequality.
- Waudby-Smith, I., Ramdas, A. (2023). Estimating means of bounded random variables by betting. *JRSS-B.* — betting confidence sequences and tests (the basis of `ville`'s `BettingTest`).
- Wang, R., Ramdas, A. (2022). False discovery rate control with e-values. *JRSS-B.* — e-BH.
- Benjamini, Y., Hochberg, Y. (1995). Controlling the false discovery rate. *JRSS-B.*
- Benjamini, Y., Yekutieli, D. (2001). The control of the false discovery rate under dependency. *Ann. Stat.*
- Politis, D., Romano, J. (1994). The stationary bootstrap. *JASA.*; Politis, D., White, H. (2004). Automatic block-length selection.
- Bailey, D., López de Prado, M. (2014). The deflated Sharpe ratio. *J. Portfolio Mgmt.* — cited for contrast.
- Loughran, T., McDonald, B. (2011). When is a liability not a liability? *J. Finance.* — sentiment lexicon.
- Killick, R., Fearnhead, P., Eckley, I. (2012). Optimal detection of changepoints with a linear computational cost. *JASA.* — PELT (`ruptures`).

## Libraries

- ville 0.1.0 — https://pypi.org/project/ville/
- expectation 0.6.1 — https://pypi.org/project/expectation/
- vectorbt 1.2 — https://pypi.org/project/vectorbt/
- arch — https://github.com/bashtage/arch
- hmmlearn — https://github.com/hmmlearn/hmmlearn
- ruptures — https://github.com/deepcharles/ruptures
- gdeltdoc — https://pypi.org/project/gdeltdoc/
- google-adk — https://github.com/google/adk-python
- Polars, DuckDB, Pydantic, statsmodels, FastAPI, lightweight-charts, ECharts.

## Market alternatives surveyed (7 Nov 2026)

- Regime (getregime.com) — crypto market-regime API. https://getregime.com/
- Build Alpha — regime signals as filters. https://www.buildalpha.com/market-regimes/
- SentimenTrader — sentiment backtester. https://sentimentrader.com/trading-tools
- Algo Studio — MT5 CUSUM drift monitor. https://algo-studio.com/
- AlgoTradingHub — live-vs-backtest drift. https://algotradinghub.io/
- Backtest auditors (look-ahead, code integrity), adjacent not competing: backtest-doctor, BacktestGuardAI, agent-backtest-lab.

## Practitioner evidence

- r/algotrading, Jan 2026: "How many live trades before you trust it and stop intervening?" (snapshot) https://reddit.sentinel-team.org/posts/1qj3gov/snapshots/2026-01-23T18%3A31%3A32.199203Z
- r/algotrading snapshot, May 2026. https://reddit.sentinel-team.org/subreddits/algotrading/snapshots/2026-05-15T19%3A02%3A50.96329Z
- r/algotrading, "Things you wish you knew before you started." https://lr.eu.psf.lt/r/algotrading/comments/1ak70xr/things_you_wish_you_knew_before_you_started
- r/algotrading, "Strategy lessons from live testing." https://lr.sudovanilla.org/r/algotrading/comments/1e4xk9m/lessons_from_live_testing/ldi9z9x/?context=3
- "From Backtest Paradise to Live Trading Hell — 5 Hard Lessons" (2026). https://judyailab.com/en/posts/backtest-to-live-trading-gap/
- r/Trading, "A few lessons learned from 10 years of algo trading." https://redlib.hyperreal.coffee/r/Trading/comments/1i8vrua/a_few_lessons_learned_from_10_years_of_algo
- Breaking Alpha, "Alpha decay detection in purchased trading strategies." https://breakingalpha.io/insights/alpha-decay-detection-purchased-trading-strategies
- Hedge Fund Alpha, "Backtesting mistakes that kill quant strategies." https://hedgefundalpha.com/education/backtesting-mistakes-kill-quant-strategies-guide/

## Hackathon

- AgentVerse 2026 site: https://agentverse.uclai.co.uk/
- Finance track slides (organisers), 7 Nov 2026: challenge, tools, deliverables, judging. Summarised in README.
