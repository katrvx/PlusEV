"""The governor: the strategy proposes, +EV disposes.

At every bar the base strategy proposes buy/hold/sell. The governor looks up the
current regime in the strategy's FROZEN envelope (learned on training paths,
confirmed on a sealed holdout). If the regime is one where the strategy has a
confirmed negative edge ("red"), entries are blocked and open positions are closed.
Everything else passes through unchanged.

No LLM here: the governor must answer in well under a second on every bar of the
hidden test, and the decision must be reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import regime as rg
from .execution import strategy_decider


class Governor:
    def __init__(self, strategy, envelope: dict, thresholds: dict):
        self.propose = strategy_decider(strategy)
        self.thresholds = thresholds
        self.red = {(b["feature"], b["bucket"]) for b in envelope["buckets"] if b["status"] == "red"}

    def decide(self, prices: list[int], shares: int) -> tuple[str, str]:
        action, why = self.propose(prices, shares)
        reg = rg.regime_at(prices, len(prices) - 1, self.thresholds)
        if reg is None:
            return action, f"{why} (warm-up, passed through)"
        hits = [f"{f}={reg[f]}" for f in rg.FEATURES if (f, reg[f]) in self.red]
        if not hits:
            return action, why
        where = ", ".join(hits)
        if action == "buy":
            return "hold", f"BLOCKED entry: regime {where} is red for this strategy"
        if shares > 0 and action == "hold":
            return "sell", f"EXIT: regime {where} is red for this strategy"
        return action, why


def load(strategy_name: str, root: Path) -> Governor:
    from .strategies import STRATEGIES

    env = json.loads((root / "envelopes" / f"{strategy_name}.json").read_text())
    thr = rg.load(root / "envelopes" / "regime_thresholds.json")
    return Governor(STRATEGIES[strategy_name], env, thr)
