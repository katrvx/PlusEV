"""What agents are allowed to propose. Anything outside this is rejected by code.

Keeping the family small and the thresholds on a fixed grid is what stops the agent
from fitting noise: it chooses among a few interpretable, pre-declared options.
"""

from __future__ import annotations

GATE_FAMILIES = ("threshold_gate",)
ALLOCATIONS = (0.0, 0.5, 1.0)

# Lagged, point-in-time features Lane A's feature store provides (spec section 7).
# fear_greed / news_sentiment are only allowed where coverage is reported >= MIN_COVERAGE.
GATE_FEATURES = ("momentum_24h", "realized_vol_7d", "volume_zscore", "fear_greed", "news_sentiment")
MIN_COVERAGE = 0.9

# Thresholds must be quantiles of the feature's TRAINING distribution, from this grid.
THRESHOLD_QUANTILES = (0.2, 0.33, 0.5, 0.67, 0.8)


def check_gate(conditions: list[dict], alloc_true: float, alloc_false: float,
               coverage: dict[str, float], train_quantiles: dict[str, dict[float, float]]) -> list[str]:
    """Return a list of violations; empty means allowed."""
    problems = []
    if alloc_true not in ALLOCATIONS or alloc_false not in ALLOCATIONS:
        problems.append(f"allocations must be in {ALLOCATIONS}")
    if alloc_true == alloc_false:
        problems.append("allocation_when_true equals allocation_when_false: not a gate")
    if not 1 <= len(conditions) <= 2:
        problems.append("1 or 2 conditions only")
    for c in conditions:
        f = c["feature"]
        if f not in GATE_FEATURES:
            problems.append(f"feature '{f}' is not allowlisted")
            continue
        if coverage.get(f, 0.0) < MIN_COVERAGE:
            problems.append(f"feature '{f}' coverage {coverage.get(f, 0.0):.0%} < {MIN_COVERAGE:.0%}")
        grid = train_quantiles.get(f, {})
        if not any(abs(c["threshold"] - v) <= 1e-9 * max(1.0, abs(v)) for v in grid.values()):
            problems.append(f"threshold {c['threshold']} for '{f}' is not on the training-quantile grid {sorted(grid.values())}")
    return problems
