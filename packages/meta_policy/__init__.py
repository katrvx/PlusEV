"""Supervisory gates. They output an allocation multiplier per decision in {0, 0.5, 1}.

They NEVER change the strategy's signals: effective exposure = multiplier * target_position,
and Lane A's simulator turns that into fills, fees and switching costs (spec section 5).
"""

from .gates import ALLOWED_MULTIPLIERS, allocation, allocation_mix, rule_gate_spec, threshold_gate_allocation
from .lgbm_gate import LGBMGate

__all__ = ["ALLOWED_MULTIPLIERS", "allocation", "allocation_mix", "rule_gate_spec", "threshold_gate_allocation", "LGBMGate"]
