"""LightGBM gate. Fit on early train, calibrate on the last 25% of train.

Validation stays untouched. The map from probability to {0, 0.5, 1} is the
train-tail base rate plus or minus a pre-registered 2 points. It is fixed
when the calibrator is fit, and it is not searched on validation or the test.
Only bars where the frozen strategy wants exposure are training rows.
"""

from __future__ import annotations

import hashlib

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
# Used only before calibrate(). The scored gate replaces these with the train-tail base rate ± BAND.
UNCALIBRATED_LOW, UNCALIBRATED_HIGH = 0.45, 0.55
BAND = 0.02


class LGBMGate:
    def __init__(self, features=DEFAULT_FEATURES, seed: int = 7, n_estimators: int = 200):
        self.features = list(features)
        self.seed = int(seed)
        self.model = lgb.LGBMClassifier(
            n_estimators=n_estimators,
            learning_rate=0.05,
            num_leaves=8,
            min_child_samples=20,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            random_state=self.seed,
            verbose=-1,
        )
        self.calibrator: IsotonicRegression | None = None
        self.fitted_on: str | None = None
        self.calibrated_on: str | None = None
        self.train_rows: int = 0
        self.base_rate: float | None = None
        self.low = UNCALIBRATED_LOW
        self.high = UNCALIBRATED_HIGH

    @staticmethod
    def _check(split: str) -> None:
        if split != "train":
            raise PermissionError(f"LGBMGate fits and calibrates on train only (got {split!r})")

    def fit(self, context: pd.DataFrame, opportunity_return: pd.Series, split: str = "train") -> "LGBMGate":
        self._check(split)
        self.model.fit(context[self.features], (opportunity_return > 0).astype(int))
        self.fitted_on = split
        self.train_rows = int(len(context))
        self.calibrator = None
        self.calibrated_on = None
        self.base_rate = None
        self.low, self.high = UNCALIBRATED_LOW, UNCALIBRATED_HIGH
        return self

    def calibrate(self, context: pd.DataFrame, opportunity_return: pd.Series, split: str = "train") -> "LGBMGate":
        self._check(split)
        if self.fitted_on is None:
            raise RuntimeError("calibrate() called before fit()")
        raw = self.model.predict_proba(context[self.features])[:, 1]
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        labels = (opportunity_return > 0).astype(int)
        self.calibrator.fit(raw, labels)
        self.base_rate = float(labels.mean())
        self.low = self.base_rate - BAND
        self.high = self.base_rate + BAND
        self.calibrated_on = "train_tail"
        return self

    def proba(self, context: pd.DataFrame) -> np.ndarray:
        raw = self.model.predict_proba(context[self.features])[:, 1]
        if self.calibrator is None:
            return raw
        return self.calibrator.predict(raw)

    def allocation(self, context: pd.DataFrame) -> pd.Series:
        probability = self.proba(context)
        out = np.where(probability > self.high, 1.0, np.where(probability < self.low, 0.0, 0.5))
        return pd.Series(out, index=context.index, dtype=float)

    def model_hash(self) -> str | None:
        """Hash of the fitted trees and the isotonic map. None before fit."""

        booster = getattr(self.model, "booster_", None)
        if booster is None:
            return None
        blob = booster.model_to_string().encode()
        if self.calibrator is not None:
            blob += np.asarray(self.calibrator.X_thresholds_, dtype=np.float64).tobytes()
            blob += np.asarray(self.calibrator.y_thresholds_, dtype=np.float64).tobytes()
        return hashlib.sha256(blob).hexdigest()[:16]

    def spec(self) -> dict:
        return {
            "policy_id": "meta::lgbm_gate_v1",
            "family": "lgbm_gate",
            "features": self.features,
            "thresholds": [self.low, self.high],
            "base_rate": self.base_rate,
            "band": BAND,
            "fitted_on": self.fitted_on,
            "calibrated_on": self.calibrated_on,
            "seed": self.seed,
            "model_hash": self.model_hash(),
        }
