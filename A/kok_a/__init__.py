"""Lane A — quant and data for Keep or Kill.

The strategy is never rewritten. This package reconstructs point-in-time
context, simulates a supervisory allocation on the next bar's open, and
returns an ExperimentResult whose field names match what Lane B consumes.
"""

from kok_a.experiment import load_for_lane_b, run_experiment

__all__ = ["load_for_lane_b", "run_experiment"]
