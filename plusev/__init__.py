"""+EV: is your trading bot still worth running?

Core idea in one line: every trade is tagged with the market regime it happened in;
a frozen statistical judge learns where a strategy makes and loses money, and a
governor uses that to let the strategy trade only where it has shown an edge.

Code computes every number and makes every decision. The LLM (later) only proposes
hypotheses and explains verdicts.
"""

__version__ = "0.1.0-mvp"
