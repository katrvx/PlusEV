"""LightGBM gate. Fit on train, calibrate on validation, never on the sealed test.

Thresholds that map probability to {0, 0.5, 1} are preselected, not searched.
Only bars where the frozen strategy wants exposure are training rows: a flat
signal has nothing to gate.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

DEFAULT_FEATURES = (
    "momentum_24h",
    "momentum_7d",
    "realized_vol_7d",
    "atr_14",
    "price_drawdown",
    "volume_zscore",
    "fear_greed",
)
LOW, HIGH = 0.45, 0.55


class LGBMGate:
    def __init__(self, features=DEFAULT_FEATURES, seed: int = 7, n_estimators: int = 200):
        self.features = list(features)
        self.model = lgb.LGBMClassifier(
            n_estimators=n_estimators,
            learning_rate=0.05,
            num_leaves=8,
            min_child_samples=20,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            random_state=seed,
            verbose=-1,
        )
        self.calibrator: IsotonicRegression | None = None
        self.fitted_on: str | None = None
        self.calibrated_on: str | None = None
        self.train_rows: int = 0

    @staticmethod
    def _check(split: str) -> None:
        if split == "test":
            raise PermissionError("LGBMGate may never fit or calibrate on the sealed test split")

    def fit(self, context: pd.DataFrame, opportunity_return: pd.Series, split: str = "train") -> "LGBMGate":
        self._check(split)
        self.model.fit(context[self.features], (opportunity_return > 0).astype(int))
        self.fitted_on = split
        self.train_rows = int(len(context))
        self.calibrator = None
        self.calibrated_on = None
        return self

    def calibrate(self, context: pd.DataFrame, opportunity_return: pd.Series, split: str = "validation") -> "LGBMGate":
        self._check(split)
        if self.fitted_on is None:
            raise RuntimeError("calibrate() called before fit()")
        raw = self.model.predict_proba(context[self.features])[:, 1]
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.calibrator.fit(raw, (opportunity_return > 0).astype(int))
        self.calibrated_on = split
        return self

    def proba(self, context: pd.DataFrame) -> np.ndarray:
        raw = self.model.predict_proba(context[self.features])[:, 1]
        if self.calibrator is None:
            return raw
        return self.calibrator.predict(raw)

    def allocation(self, context: pd.DataFrame) -> pd.Series:
        probability = self.proba(context)
        out = np.where(probability > HIGH, 1.0, np.where(probability < LOW, 0.0, 0.5))
        return pd.Series(out, index=context.index, dtype=float)

    def spec(self) -> dict:
        return {
            "policy_id": "meta::lgbm_gate_v1",
            "family": "lgbm_gate",
            "features": self.features,
            "thresholds": [LOW, HIGH],
            "fitted_on": self.fitted_on,
            "calibrated_on": self.calibrated_on,
        }
