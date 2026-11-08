"""Offline walk-forward replay of one kit market case (our code, not the kit).

`kit` execution mirrors the kit's market runner exactly (decision on prices[0..t],
fill at bar t+1 with fixed fee and adverse slippage, all-in long or flat, forced
final sale) and is cross-checked against the kit's own final cash per path.

`fractional` execution is our extension for the exact champion rule: integer
shares sized to target * equity, so a 0.5 target really holds about half.
It is NOT the kit's runner; results from it are labelled as such.
"""

from __future__ import annotations

from typing import Callable

from . import rule

TargetFn = Callable[[list[int]], float]  # prices[0..t] -> target for bar t


def target_fn(strategy: str, mode: str) -> TargetFn:
    return lambda prices: float(rule.target_positions(strategy, mode, prices)[-1])


def simulate(data: dict, target: TargetFn, execution: str = "kit") -> dict:
    prices = data["prices_pence"]
    cash = start = data["initial_cash_pence"]
    fee, bps = data["fee_pence"], data["slippage_bps"]
    shares, held = 0, 0.0
    equity, exposure = [cash], []
    for t in range(len(prices) - 1):
        b = target(prices[: t + 1])
        nxt = prices[t + 1]
        buy_fill = (nxt * (10000 + bps) + 9999) // 10000
        sell_fill = nxt * (10000 - bps) // 10000
        if execution == "kit":
            action = rule.kit_action(b, shares)
            if action == "buy":
                units = max(0, cash - fee) // buy_fill
                if units:
                    cash -= units * buy_fill + fee
                    shares += units
            elif action == "sell":
                cash += shares * sell_fill - fee
                shares = 0
        elif execution == "fractional":
            if b != held:
                if b >= 1.0:
                    desired = shares + max(0, cash - fee) // buy_fill
                elif b <= 0.0:
                    desired = 0
                else:
                    desired = int(b * (cash + shares * nxt)) // nxt
                if desired > shares:
                    units = min(desired - shares, max(0, cash - fee) // buy_fill)
                    if units:
                        cash -= units * buy_fill + fee
                        shares += units
                elif desired < shares:
                    cash += (shares - desired) * sell_fill - fee
                    shares = desired
                held = b if (shares > 0 or b <= 0.0) else 0.0  # a failed buy is retried next bar
        else:
            raise ValueError(execution)
        if cash < 0:
            raise ValueError("cash went negative")
        value = cash + shares * nxt
        exposure.append(shares * nxt / value if value else 0.0)
        equity.append(value)
    if shares:
        cash += shares * (prices[-1] * (10000 - bps) // 10000) - fee
        shares = 0
    equity.append(cash)
    peak, mdd = equity[0], 0
    for v in equity:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) * 10000 // peak)
    return {
        "final_cash_pence": cash,
        "return": (cash - start) / start,
        "max_drawdown_bps": mdd,
        "mean_exposure": sum(exposure) / len(exposure) if exposure else 0.0,
        "exposure_bars": exposure,
    }
