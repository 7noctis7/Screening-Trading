"""Modèles ML — interface commune + baseline numpy + adaptateur sklearn/xgboost.

LogitModel : régression logistique en numpy pur (imputation + standardisation +
descente de gradient L2) → AUCUNE dépendance, toujours testable. SklearnModel/XGBoost :
adaptateurs pour la prod. Tous exposent fit / predict_proba / predict.
"""

from __future__ import annotations

import numpy as np


class LogitModel:
    name = "logit_numpy"

    def __init__(self, lr: float = 0.1, epochs: int = 300, l2: float = 1e-3) -> None:
        self.lr, self.epochs, self.l2 = lr, epochs, l2
        self.w = self.b = None
        self._mean = self._std = self._impute = None

    def _prep(self, X: np.ndarray, fit: bool) -> np.ndarray:
        X = np.asarray(X, float)
        if fit:
            self._impute = np.nanmean(X, axis=0)
        X = np.where(np.isnan(X), self._impute, X)
        if fit:
            self._mean, self._std = X.mean(0), X.std(0) + 1e-9
        return (X - self._mean) / self._std

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LogitModel":
        Xs = self._prep(X, fit=True)
        y = np.asarray(y, float)
        n, d = Xs.shape
        self.w, self.b = np.zeros(d), 0.0
        for _ in range(self.epochs):
            p = _sigmoid(Xs @ self.w + self.b)
            err = p - y
            self.w -= self.lr * (Xs.T @ err / n + self.l2 * self.w)
            self.b -= self.lr * err.mean()
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return _sigmoid(self._prep(X, fit=False) @ self.w + self.b)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X) >= 0.5).astype(int)


class SklearnModel:
    name = "sklearn"

    def __init__(self, estimator=None) -> None:
        if estimator is None:
            from sklearn.ensemble import GradientBoostingClassifier
            estimator = GradientBoostingClassifier(n_estimators=80, max_depth=3)
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        self.pipe = Pipeline([("impute", SimpleImputer(strategy="mean")),
                              ("clf", estimator)])

    def fit(self, X, y):
        self.pipe.fit(X, y); return self

    def predict_proba(self, X):
        return self.pipe.predict_proba(X)[:, 1]

    def predict(self, X):
        return self.pipe.predict(X)


def make_model(kind: str = "logit", **kw):
    if kind == "logit":
        return LogitModel(**kw)
    if kind == "sklearn":
        return SklearnModel(**kw)
    if kind == "xgboost":
        from xgboost import XGBClassifier  # adaptateur prod
        return SklearnModel(XGBClassifier(n_estimators=100, max_depth=3,
                                          use_label_encoder=False, eval_metric="logloss"))
    raise ValueError(f"modèle inconnu: {kind}")


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
