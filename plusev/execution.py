"""Our own re-implementation of the organisers' paper-trading rules.

Same rules as the kit's walk-forward runner: the decision at bar t uses prices[0..t],
the order fills at bar t+1, all-in long only, integer shares, fixed fee in pence,
adverse slippage in basis points, forced sale at the last price. We do NOT import
the kit; a test checks our final cash equals the kit's.

Every completed round trip becomes a trade record tagged with the regime at the
bar where the entry signal fired.
"""

from __future__ import annotations

from typing import Callable

from . import regime as rg

# decide(prices_so_far, shares_held) -> "buy" | "hold" | "sell", plus a reason
Decider = Callable[[list[int], int], tuple[str, str]]


def strategy_decider(strategy) -> Decider:
    def decide(prices: list[int], shares: int) -> tuple[str, str]:
        holding = shares > 0
        want = strategy(prices, holding)
        if want and not holding:
            return "buy", "strategy entry signal"
        if not want and holding:
            return "sell", "strategy exit signal"
        return "hold", "no change"

    return decide


def simulate(case: dict, decide: Decider, thresholds: dict, path_id: str = "") -> dict:
    """Walk forward through one path. Returns trades, equity curve, decisions, final cash."""
    prices = case["prices_pence"]
    cash = case["initial_cash_pence"]
    fee, bps = case["fee_pence"], case["slippage_bps"]
    shares, fees_paid = 0, 0
    equity = [cash]
    decisions, trades = [], []
    open_trade = None

    for t in range(len(prices) - 1):
        action, reason = decide(prices[: t + 1], shares)
        decisions.append({"bar": t, "action": action, "reason": reason})
        nxt = prices[t + 1]
        if action == "buy" and shares == 0:
            fill = (nxt * (10000 + bps) + 9999) // 10000
            units = max(0, cash - fee) // fill
            if units:
                cost = units * fill + fee
                cash -= cost
                shares = units
                fees_paid += fee
                open_trade = {
                    "path_id": path_id,
                    "entry_signal_bar": t,
                    "entry_fill_bar": t + 1,
                    "entry_signal_px": prices[t],
                    "entry_fill_px": fill,
                    "units": units,
                    "entry_cost_pence": cost,
                    "regime": rg.regime_at(prices, t, thresholds),
                }
        elif action == "sell" and shares:
            fill = nxt * (10000 - bps) // 10000
            proceeds = shares * fill - fee
            cash += proceeds
            fees_paid += fee
            trades.append(_close(open_trade, t, t + 1, prices[t], fill, proceeds))
            shares, open_trade = 0, None
        equity.append(cash + shares * nxt)

    if shares:
        fill = prices[-1] * (10000 - bps) // 10000
        proceeds = shares * fill - fee
        cash += proceeds
        fees_paid += fee
        last = len(prices) - 1
        trades.append(_close(open_trade, last, last, prices[-1], fill, proceeds))
        shares = 0
    equity.append(cash)

    peak, mdd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)

    return {
        "final_cash_pence": cash,
        "profit_pence": cash - case["initial_cash_pence"],
        "max_drawdown": mdd,
        "fees_paid_pence": fees_paid,
        "equity": equity,
        "decisions": decisions,
        "trades": trades,
    }


def _close(tr: dict, signal_bar: int, fill_bar: int, signal_px: int, fill_px: int, proceeds: int) -> dict:
    units = tr["units"]
    gross = units * (signal_px - tr["entry_signal_px"])
    net = proceeds - tr["entry_cost_pence"]
    return {
        **tr,
        "exit_signal_bar": signal_bar,
        "exit_fill_bar": fill_bar,
        "exit_signal_px": signal_px,
        "exit_fill_px": fill_px,
        "gross_pnl_pence": gross,
        "net_pnl_pence": net,
        "net_return": net / tr["entry_cost_pence"],
        "gross_return": gross / (units * tr["entry_signal_px"]),
    }


def buy_and_hold(case: dict) -> int:
    """Final cash for buying at bar 1's price (signal at bar 0) and holding to the end."""
    prices, cash = case["prices_pence"], case["initial_cash_pence"]
    fee, bps = case["fee_pence"], case["slippage_bps"]
    fill = (prices[1] * (10000 + bps) + 9999) // 10000
    units = max(0, cash - fee) // fill
    if not units:
        return cash
    cash -= units * fill + fee
    return cash + units * (prices[-1] * (10000 - bps) // 10000) - fee
