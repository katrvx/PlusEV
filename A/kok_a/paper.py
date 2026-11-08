"""14-day hourly shadow log.

The sealed test stays where it is. This log starts only after a person approves
the frozen champion and challenger. 336 bars is 14 days on the hourly rail.
A full path inside the training range is INCONCLUSIVE. A full path outside it
is MONITOR. Neither one retunes the experiment.
"""

from __future__ import annotations

import pandas as pd

from kok_a.contracts import PaperFill, PaperPlan

HOURLY_HORIZON_BARS = 14 * 24


def open_shadow(plan: PaperPlan) -> PaperPlan:
    """Approval opens the log. It does not invent fills."""

    if plan.approved and plan.status != "recorded_not_started":
        return plan
    return plan.model_copy(update={"approved": True, "status": "awaiting_bars", "completed": False})


def record_shadow(plan: PaperPlan, rows: pd.DataFrame) -> PaperPlan:
    """Append closed hourly bars. Extra bars past 14 days are left out."""

    if not plan.approved:
        raise RuntimeError("A person has to approve the frozen pair before the shadow log records a bar.")
    horizon = plan.predictive_horizon_bars or HOURLY_HORIZON_BARS
    if horizon != HOURLY_HORIZON_BARS:
        raise RuntimeError(f"the hourly shadow log expects {HOURLY_HORIZON_BARS} bars, got {horizon}")
    frame = rows.copy()
    fills: list[PaperFill] = []
    if len(frame):
        frame["decision_time"] = pd.to_datetime(frame["decision_time"], utc=True)
        frame = frame.sort_values("decision_time").head(horizon)
        fills = [
            PaperFill(
                decision_time=stamp.to_pydatetime(),
                champion_position=float(row.champion_position),
                challenger_position=float(row.challenger_position),
                fill_open=float(row.fill_open),
                champion_net=float(row.champion_net),
                challenger_net=float(row.challenger_net),
                fee=float(row.fee),
                slippage=float(row.slippage),
            )
            for stamp, row in zip(frame["decision_time"], frame.itertuples(index=False), strict=True)
        ]
    if not fills:
        return plan.model_copy(
            update={
                "status": "awaiting_bars",
                "completed": False,
                "fills": [],
                "champion_net_return": None,
                "challenger_net_return": None,
                "range_position": None,
                "paper_conclusion": None,
            }
        )
    champion = _compound([item.champion_net for item in fills])
    challenger = _compound([item.challenger_net for item in fills])
    if len(fills) < horizon:
        return plan.model_copy(
            update={
                "status": "running",
                "completed": False,
                "fills": fills,
                "champion_net_return": champion,
                "challenger_net_return": challenger,
                "range_position": "incomplete",
                "paper_conclusion": None,
            }
        )
    watched = champion if plan.champion_policy_id == "always_on" or plan.challenger_policy_id != "always_on" else challenger
    position, conclusion = _judge(watched, plan.predictive_range_low, plan.predictive_range_high)
    return plan.model_copy(
        update={
            "status": "completed",
            "completed": True,
            "fills": fills,
            "champion_net_return": champion,
            "challenger_net_return": challenger,
            "range_position": position,
            "paper_conclusion": conclusion,
        }
    )


def _compound(values: list[float]) -> float:
    out = 1.0
    for value in values:
        out *= 1.0 + value
    return out - 1.0


def _judge(net: float, low: float | None, high: float | None) -> tuple[str, str]:
    if low is None or high is None or not (low < high):
        return "incomplete", "INCONCLUSIVE"
    if low <= net <= high:
        return "inside", "INCONCLUSIVE"
    if net < low:
        return "below", "MONITOR"
    return "above", "MONITOR"
