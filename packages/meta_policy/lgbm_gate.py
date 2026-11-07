"""LightGBM meta-model gate (spec section 8, model 4).

Estimates P(strategy's next-interval net opportunity return > 0 | point-in-time context).
- fitted on TRAIN rows only;
- probability calibrated on VALIDATION (isotonic on a frozen model);
- converted to {0, 0.5, 1} with thresholds PRESELECTED here, never tuned on any split;
- refuses to fit or calibrate on anything labelled 'test'.
Only decisions where the strategy wants exposure are used: if the base signal is flat
there is nothing to gate.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

DEFAULT_FEATURES = ("momentum_24h", "realized_vol_7d", "volume_zscore", "fear_greed")
LOW, HIGH = 0.45, 0.55        # preselected: p < LOW -> 0, LOW..HIGH -> 0.5, p > HIGH -> 1


class LGBMGate:
    def __init__(self, features=DEFAULT_FEATURES, seed: int = 7):
        self.features = list(features)
        self.model = lgb.LGBMClassifier(
            n_estimators=200, learning_rate=0.03, num_leaves=8, min_child_samples=80,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
            random_state=seed, verbose=-1,
        )
        self.calibrator: IsotonicRegression | None = None
        self.fitted_on: str | None = None
        self.calibrated_on: str | None = None

    @staticmethod
    def _check(split: str) -> None:
        if split == "test":
            raise PermissionError("LGBMGate may never fit or calibrate on the sealed test split")

    def fit(self, context: pd.DataFrame, opportunity_return: pd.Series, split: str = "train") -> "LGBMGate":
        self._check(split)
        X, y = context[self.features], (opportunity_return > 0).astype(int)
        self.model.fit(X, y)
        self.fitted_on = split
        return self

    def calibrate(self, context: pd.DataFrame, opportunity_return: pd.Series, split: str = "validation") -> "LGBMGate":
        self._check(split)
        raw = self.model.predict_proba(context[self.features])[:, 1]
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(raw, (opportunity_return > 0).astype(int))
        self.calibrated_on = split
        return self

    def proba(self, context: pd.DataFrame) -> np.ndarray:
        raw = self.model.predict_proba(context[self.features])[:, 1]
        return self.calibrator.predict(raw) if self.calibrator is not None else raw

    def allocation(self, context: pd.DataFrame) -> pd.Series:
        p = self.proba(context)
        out = np.where(p > HIGH, 1.0, np.where(p < LOW, 0.0, 0.5))
        return pd.Series(out, index=context.index, dtype=float)

    def feature_importance(self) -> dict[str, float]:
        imp = self.model.booster_.feature_importance(importance_type="gain")
        total = float(imp.sum()) or 1.0
        return {f: float(v) / total for f, v in zip(self.features, imp)}

    def spec(self) -> dict:
        return {"policy_id": "meta::lgbm_gate_v1", "family": "lgbm_gate", "features": self.features,
                "thresholds": [LOW, HIGH], "fitted_on": self.fitted_on, "calibrated_on": self.calibrated_on}
