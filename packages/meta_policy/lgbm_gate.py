"""LightGBM meta-model gate (spec section 8, model 4).

Estimates P(strategy's next-interval return while exposed > 0 | point-in-time context).
- fitted on the EARLY part of TRAIN, probability calibrated (isotonic) on the LATE part
  of TRAIN: validation stays untouched, so the gate's validation result is out-of-sample;
- converted to {0, 0.5, 1} with a band PRESELECTED relative to the calibration base rate
  (base - BAND, base + BAND), never tuned on any split;
- refuses to fit or calibrate on anything labelled 'test' or 'validation'.
Label caveat: gross next-interval return (costs arise only when the multiplier changes,
which the simulator charges). Only decisions where the strategy wants exposure are used.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

DEFAULT_FEATURES = ("momentum_24h", "realized_vol_7d", "volume_zscore", "fear_greed")
BAND = 0.02               # preselected half-width around the calibration base rate
CALIBRATION_SHARE = 0.25  # last 25% of train (chronological) is used for calibration


class LGBMGate:
    def __init__(self, features=DEFAULT_FEATURES, seed: int = 7):
        self.features = list(features)
        self.model = lgb.LGBMClassifier(
            n_estimators=200, learning_rate=0.03, num_leaves=8, min_child_samples=80,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
            random_state=seed, verbose=-1,
        )
        self.calibrator: IsotonicRegression | None = None
        self.low, self.high = 0.45, 0.55
        self.base_rate: float | None = None
        self.fitted_on: str | None = None

    @staticmethod
    def _check(split: str) -> None:
        if split != "train":
            raise PermissionError(f"LGBMGate fits and calibrates on train only (got '{split}')")

    def fit(self, context: pd.DataFrame, opportunity_return: pd.Series, split: str = "train") -> "LGBMGate":
        """Chronological: first (1 - CALIBRATION_SHARE) of rows to fit, the rest to calibrate."""
        self._check(split)
        n = len(context)
        cut = int(n * (1 - CALIBRATION_SHARE))
        X, y = context[self.features], (opportunity_return > 0).astype(int)
        self.model.fit(X.iloc[:cut], y.iloc[:cut])
        raw = self.model.predict_proba(X.iloc[cut:])[:, 1]
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(raw, y.iloc[cut:])
        self.base_rate = float(y.iloc[cut:].mean())
        self.low, self.high = self.base_rate - BAND, self.base_rate + BAND
        self.fitted_on = f"train[:{cut}] fit, train[{cut}:] calibrate"
        return self

    def proba(self, context: pd.DataFrame) -> np.ndarray:
        raw = self.model.predict_proba(context[self.features])[:, 1]
        return self.calibrator.predict(raw) if self.calibrator is not None else raw

    def allocation(self, context: pd.DataFrame) -> pd.Series:
        p = self.proba(context)
        out = np.where(p > self.high, 1.0, np.where(p < self.low, 0.0, 0.5))
        return pd.Series(out, index=context.index, dtype=float)

    def feature_importance(self) -> dict[str, float]:
        imp = self.model.booster_.feature_importance(importance_type="gain")
        total = float(imp.sum()) or 1.0
        return {f: float(v) / total for f, v in zip(self.features, imp)}

    def spec(self) -> dict:
        return {"policy_id": "meta::lgbm_gate_v1", "family": "lgbm_gate", "features": self.features,
                "band": [self.low, self.high], "base_rate": self.base_rate, "fitted_on": self.fitted_on}
