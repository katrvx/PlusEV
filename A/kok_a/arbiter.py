"""Deterministic keep-or-kill decision. No model output is consulted.

Rules are pre-registered. A positive point estimate whose interval still
contains zero is INCONCLUSIVE. A drawdown past the cap cannot be overruled
into KEEP or ACTIVATE CONDITIONALLY. COMBINE is out of scope: one experiment
is one strategy.
"""

from __future__ import annotations

import math

from kok_a.contracts import Decision, GateEvaluation, PaperPlan

MIN_TEST_DECISIONS = 150
DRAWDOWN_CAP = 0.40
DRAWDOWN_SLACK = 0.05
MIN_PARTICIPATION = 0.05
MAX_PARTICIPATION = 0.95
CHALLENGERS = ("simple_rule", "lgbm_gate")
REQUIRED = ("always_on", "cash", "simple_rule", "lgbm_gate")


def decide(by_policy: dict[str, GateEvaluation], n_test: int) -> Decision:
    missing = [name for name in REQUIRED if name not in by_policy]
    if missing:
        raise KeyError(f"arbiter needs {missing}")
    for name, evaluation in by_policy.items():
        if evaluation.split != "test":
            raise ValueError(f"{name} was scored on {evaluation.split}, not the sealed test")

    always = by_policy["always_on"]
    evidence = _evidence(by_policy, n_test)
    if n_test < MIN_TEST_DECISIONS:
        return _decision(
            "INCONCLUSIVE",
            "always_on",
            [f"Test window has {n_test} decisions. The pre-registered minimum is {MIN_TEST_DECISIONS}."],
            evidence,
        )

    qualified = [by_policy[name] for name in CHALLENGERS if _beats_always_on(by_policy[name], always)]
    if qualified:
        best = max(qualified, key=lambda item: item.delta_net_return_vs_always_on)
        return _decision(
            "ACTIVATE CONDITIONALLY",
            best.policy_id,
            [
                f"{best.policy_id} beat always-on on the sealed test. "
                "The 90% interval on the cost-adjusted difference is entirely above zero, "
                "and its drawdown stays inside the cap.",
            ],
            evidence,
        )

    risky = [by_policy[name] for name in CHALLENGERS if _would_activate_except_for_drawdown(by_policy[name], always)]
    if risky:
        names = ", ".join(item.policy_id for item in risky)
        return _decision(
            "MONITOR",
            "always_on",
            [
                f"{names} improved on always-on, but max drawdown is above the {DRAWDOWN_CAP:.0%} cap. "
                "The risk limit blocks activation.",
            ],
            evidence,
            risk_override=True,
        )

    if always.metrics.max_drawdown > DRAWDOWN_CAP and _ci_entirely_below_zero(always.metrics.ci_net_return):
        return _decision(
            "KILL",
            "cash",
            [
                f"Always-on drawdown {always.metrics.max_drawdown:.1%} exceeds the {DRAWDOWN_CAP:.0%} cap, "
                "and the interval on its net return is entirely below zero.",
            ],
            evidence,
            risk_override=True,
        )

    if always.metrics.max_drawdown > DRAWDOWN_CAP:
        rule = by_policy["simple_rule"]
        if rule.metrics.exposure < always.metrics.exposure and rule.metrics.max_drawdown <= DRAWDOWN_CAP:
            return _decision(
                "REDUCE",
                rule.policy_id,
                [
                    f"Always-on drawdown {always.metrics.max_drawdown:.1%} exceeds the {DRAWDOWN_CAP:.0%} cap. "
                    "The simple rule participates less and stays inside the cap. "
                    "That is a risk reduction, not a proven improvement.",
                ],
                evidence,
                risk_override=True,
            )
        return _decision(
            "MONITOR",
            "always_on",
            [
                f"Always-on drawdown {always.metrics.max_drawdown:.1%} exceeds the {DRAWDOWN_CAP:.0%} cap, "
                "and no allowlisted gate both reduces participation and stays inside the cap.",
            ],
            evidence,
            risk_override=True,
        )

    if _ci_entirely_above_zero(always.metrics.ci_net_return):
        return _decision(
            "KEEP",
            "always_on",
            [
                "Always-on's net-return interval is entirely above zero, "
                "and no gate beat it with an interval that excludes zero.",
            ],
            evidence,
        )

    if _ci_entirely_below_zero(always.metrics.ci_net_return):
        return _decision(
            "KILL",
            "cash",
            ["Always-on's net-return interval is entirely below zero after costs. Cash is the benchmark."],
            evidence,
        )

    return _decision(
        "INCONCLUSIVE",
        "always_on",
        [
            "The sealed-test intervals still contain zero. "
            "A point estimate is not enough to keep, gate, or kill the strategy.",
        ],
        evidence,
    )


def build_paper_plan(
    experiment_id: str,
    strategy_id: str,
    strategy_version: str,
    decision: Decision,
    cost_assumptions: str,
) -> PaperPlan:
    challenger = decision.policy_id if decision.policy_id != "always_on" else "simple_rule"
    return PaperPlan(
        plan_id=f"paper_{experiment_id}",
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        champion_policy_id="always_on",
        challenger_policy_id=challenger,
        frozen_at_experiment=experiment_id,
        cost_assumptions=cost_assumptions,
        notes=[
            "Recorded plan for a 14-day shadow run. It has not been started and it is not a result.",
            "approved is false until a person accepts this frozen champion and challenger.",
            "Retuning either policy after the window starts is a new experiment, not an edit of this plan.",
            "COMBINE is not offered. This experiment contains one strategy.",
            f"Arbiter verdict at freeze: {decision.verdict}. Recommended policy: {decision.policy_id}.",
        ],
    )


def _beats_always_on(evaluation: GateEvaluation, always: GateEvaluation) -> bool:
    metrics = evaluation.metrics
    return (
        _ci_entirely_above_zero(evaluation.ci_delta)
        and evaluation.delta_net_return_vs_always_on > 0
        and MIN_PARTICIPATION < metrics.exposure < MAX_PARTICIPATION
        and metrics.max_drawdown <= always.metrics.max_drawdown + DRAWDOWN_SLACK
        and metrics.max_drawdown <= DRAWDOWN_CAP
    )


def _would_activate_except_for_drawdown(evaluation: GateEvaluation, always: GateEvaluation) -> bool:
    metrics = evaluation.metrics
    return (
        _ci_entirely_above_zero(evaluation.ci_delta)
        and evaluation.delta_net_return_vs_always_on > 0
        and MIN_PARTICIPATION < metrics.exposure < MAX_PARTICIPATION
        and metrics.max_drawdown <= always.metrics.max_drawdown + DRAWDOWN_SLACK
        and metrics.max_drawdown > DRAWDOWN_CAP
    )


def _ci_entirely_above_zero(interval: tuple[float, float] | None) -> bool:
    if not _finite(interval):
        return False
    assert interval is not None
    return interval[0] > 0


def _ci_entirely_below_zero(interval: tuple[float, float] | None) -> bool:
    if not _finite(interval):
        return False
    assert interval is not None
    return interval[1] < 0


def _finite(interval: tuple[float, float] | None) -> bool:
    return interval is not None and all(math.isfinite(bound) for bound in interval)


def _evidence(by_policy: dict[str, GateEvaluation], n_test: int) -> dict[str, float]:
    always = by_policy["always_on"].metrics
    found = {
        "n_test": float(n_test),
        "always_on_net": always.net_return,
        "always_on_max_drawdown": always.max_drawdown,
        "always_on_exposure": always.exposure,
    }
    for name in CHALLENGERS:
        evaluation = by_policy[name]
        found[f"{name}_delta"] = evaluation.delta_net_return_vs_always_on
        found[f"{name}_max_drawdown"] = evaluation.metrics.max_drawdown
        found[f"{name}_exposure"] = evaluation.metrics.exposure
    return found


def _decision(
    verdict: str,
    policy_id: str,
    reasons: list[str],
    evidence: dict[str, float],
    risk_override: bool = False,
) -> Decision:
    return Decision(
        verdict=verdict,  # type: ignore[arg-type]
        policy_id=policy_id,
        reasons=reasons,
        risk_override=risk_override,
        evidence=evidence,
    )
