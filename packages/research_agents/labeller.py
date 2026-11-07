"""Optional semantic news labelling (AGENTS.md Lane B step 6).

Batch, offline, cached by content hash. The labeller sees only the headline text, never
prices, returns or dates, so it cannot leak outcomes. Two implementations:
  LLMLabeller      PydanticAI agent with structured output (model from KOK_AGENT_MODEL)
  LexiconLabeller  tiny keyword baseline; the LLM must beat it to be worth using
"""

from __future__ import annotations

import re

from pydantic_ai import Agent

from .news import NewsLabel

TOPIC_WORDS = {
    "regulatory": r"\b(sec|regulat\w*|ban\w*|lawsuit|court|compliance|etf approval|license)\b",
    "macro": r"\b(fed|rate\w*|inflation|cpi|jobs|gdp|recession|yield\w*)\b",
    "exchange_failure": r"\b(hack\w*|exploit\w*|outage|insolven\w*|withdrawals? halted|bankrupt\w*)\b",
    "institutional_flows": r"\b(etf flows?|inflows?|outflows?|treasury|fund\w*|blackrock|institution\w*)\b",
    "risk_on_off": r"\b(rally|sell-?off|risk[- ]?(on|off)|crash\w*|surge\w*)\b",
}
POS = r"\b(approv\w*|surge\w*|rally|inflows?|record high|gain\w*|beat\w*)\b"
NEG = r"\b(ban\w*|hack\w*|crash\w*|outflows?|lawsuit|plunge\w*|halt\w*|fraud|miss\w*)\b"


class LexiconLabeller:
    name = "lexicon-v1"

    def label(self, title: str) -> NewsLabel:
        t = title.lower()
        topic = next((k for k, rx in TOPIC_WORDS.items() if re.search(rx, t)), "other")
        pos, neg = len(re.findall(POS, t)), len(re.findall(NEG, t))
        pol = 0.0 if pos == neg else (pos - neg) / (pos + neg)
        return NewsLabel(topic=topic, polarity=pol, confidence=0.3 if topic == "other" else 0.5, labeller=self.name)


class LLMLabeller:
    def __init__(self, model: str):
        self.name = f"llm:{model}"
        self.agent = Agent(model, output_type=NewsLabel, defer_model_check=True, instructions=(
            "Classify a single financial news headline. topic: one of risk_on_off, regulatory, macro, exchange_failure, "
            "institutional_flows, other. polarity: -1 (clearly negative for crypto prices) to +1 (clearly positive). "
            "confidence: 0-1. Use only the headline; do not guess the date or what happened afterwards. "
            f"Set labeller to '{self.name}'."))

    def label(self, title: str) -> NewsLabel:
        out = self.agent.run_sync(f"Headline: {title}").output
        return out.model_copy(update={"labeller": self.name})
