"""Supervisory gates. They output an allocation multiplier per decision in {0, 0.5, 1}.

They NEVER change the strategy's signals: effective exposure = multiplier * target_position,
and Lane A's simulator turns that into fills, fees and switching costs (spec section 5).
"""

from __future__ import annotations

from .gates import ALLOWED_MULTIPLIERS, allocation, allocation_mix, rule_gate_spec, threshold_gate_allocation
try:  # LightGBM needs a native OpenMP runtime (libomp on macOS); everything else works without it
    from .lgbm_gate import LGBMGate
    LGBM_UNAVAILABLE: str | None = None
except (ImportError, OSError) as _exc:  # pragma: no cover - platform dependent
    LGBMGate = None  # type: ignore[assignment,misc]
    LGBM_UNAVAILABLE = f"{type(_exc).__name__}: {str(_exc).splitlines()[0][:200]}"

__all__ = ["ALLOWED_MULTIPLIERS", "allocation", "allocation_mix", "rule_gate_spec", "threshold_gate_allocation", "LGBMGate",
           "LGBM_UNAVAILABLE"]
