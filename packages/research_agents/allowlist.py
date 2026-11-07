"""What agents are allowed to propose. Anything outside this is rejected by code.

Keeping the family small and the thresholds on a fixed grid is what stops the agent
from fitting noise: it chooses among a few interpretable, pre-declared options.
"""

from __future__ import annotations

import math

GATE_FAMILIES = ("threshold_gate",)
ALLOCATIONS = (0.0, 0.5, 1.0)
OPS = ("<=", ">")

# Lagged, point-in-time features Lane A's feature store provides (spec section 7).
# fear_greed / news_sentiment are only allowed where coverage is reported >= MIN_COVERAGE.
GATE_FEATURES = ("momentum_24h", "realized_vol_7d", "volume_zscore", "fear_greed", "news_sentiment")
MIN_COVERAGE = 0.9

# Thresholds must be quantiles of the feature's TRAINING distribution, from this grid.
THRESHOLD_QUANTILES = (0.2, 0.33, 0.5, 0.67, 0.8)


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def check_gate(conditions, alloc_true, alloc_false, coverage: dict[str, float],
               train_quantiles: dict[str, dict[float, float]]) -> list[str]:
    """Return a list of violations; empty means allowed. Never raises on malformed input."""
    problems = []
    if not (_is_number(alloc_true) and _is_number(alloc_false)) or alloc_true not in ALLOCATIONS or alloc_false not in ALLOCATIONS:
        problems.append(f"allocations must be numbers in {ALLOCATIONS}")
    elif alloc_true == alloc_false:
        problems.append("allocation_when_true equals allocation_when_false: not a gate")
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 2:
        problems.append("1 or 2 conditions only")
        return problems
    seen = set()
    for c in conditions:
        if not isinstance(c, dict) or not {"feature", "op", "threshold"} <= set(c):
            problems.append(f"condition {c!r} must have feature, op, threshold")
            continue
        f, op, thr = c["feature"], c["op"], c["threshold"]
        if op not in OPS:
            problems.append(f"op {op!r} not allowed; use one of {OPS}")
        if not _is_number(thr):
            problems.append(f"threshold {thr!r} must be a finite number")
            continue
        if (f, op) in seen:
            problems.append(f"duplicate condition on {f} {op}")
        seen.add((f, op))
        if f not in GATE_FEATURES:
            problems.append(f"feature '{f}' is not allowlisted")
            continue
        if coverage.get(f, 0.0) < MIN_COVERAGE:
            problems.append(f"feature '{f}' coverage {coverage.get(f, 0.0):.0%} < {MIN_COVERAGE:.0%}")
        grid = train_quantiles.get(f, {})
        if not any(abs(thr - v) <= 1e-9 * max(1.0, abs(v)) for v in grid.values()):
            problems.append(f"threshold {thr} for '{f}' is not on the training-quantile grid {sorted(grid.values())}")
    return problems
