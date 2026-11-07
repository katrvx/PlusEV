"""Three deliberately simple base strategies. +EV judges them; it does not invent them.

Each strategy is a pure function: (prices observed so far, currently holding?) -> want to hold?
"""

from __future__ import annotations


def _sma(xs: list[int], n: int) -> float:
    return sum(xs[-n:]) / n


def mean_reversion(prices: list[int], holding: bool) -> bool:
    """Buy a dip below the 10-bar mean; exit when price is back at the mean."""
    if len(prices) < 10:
        return holding
    window = prices[-10:]
    mean = sum(window) / 10
    sd = (sum((p - mean) ** 2 for p in window) / 9) ** 0.5 or 1.0
    z = (prices[-1] - mean) / sd
    if not holding:
        return z < -1.0
    return z < 0.0


def trend(prices: list[int], holding: bool) -> bool:
    """Hold while the 3-bar average is above the 8-bar average."""
    if len(prices) < 8:
        return holding
    return _sma(prices, 3) > _sma(prices, 8)


def breakout(prices: list[int], holding: bool) -> bool:
    """Buy a new 8-bar high; exit on a new 5-bar low."""
    if len(prices) < 9:
        return holding
    if not holding:
        return prices[-1] > max(prices[-9:-1])
    return not prices[-1] < min(prices[-6:-1])


STRATEGIES = {
    "mean_reversion": mean_reversion,
    "trend": trend,
    "breakout": breakout,
}

DESCRIPTIONS = {
    "mean_reversion": "Buys when price drops more than one standard deviation below its 10-bar average, sells when it returns to the average.",
    "trend": "Holds the asset while the 3-bar moving average is above the 8-bar moving average.",
    "breakout": "Buys when price makes a new 8-bar high, sells on a new 5-bar low.",
}
