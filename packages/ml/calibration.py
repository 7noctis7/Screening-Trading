"""Calibration des probabilités — fiabilité des scores ML (best practice López de Prado / sklearn).

Un modèle peut bien classer (AUC élevé) tout en étant mal **calibré** (une proba 0.8 ne se
réalise pas 80 % du temps). On fournit :
- **Platt scaling** (régression logistique 1-D, numpy pur) ;
- **Brier score** (erreur quadratique des probas) + courbe de fiabilité (bins).
Numpy pur, testable hors-ligne, repli gracieux.
"""

from __future__ import annotations

import numpy as np


def brier_score(y_true, p_pred) -> float:
    """Brier score (plus bas = mieux). 0 = parfait, 0.25 = aléatoire (base rate 0.5)."""
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(p_pred, dtype=float), 0.0, 1.0)
    if y.size == 0:
        return 0.0
    return round(float(np.mean((p - y) ** 2)), 4)


def reliability_curve(y_true, p_pred, bins: int = 10) -> list[dict]:
    """Courbe de fiabilité : proba moyenne prédite vs fréquence observée par bin."""
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(p_pred, dtype=float), 0.0, 1.0)
    out: list[dict] = []
    if y.size == 0:
        return out
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    for b in range(bins):
        m = idx == b
        if m.sum() == 0:
            continue
        out.append({"pred": round(float(p[m].mean()), 3),
                    "obs": round(float(y[m].mean()), 3), "n": int(m.sum())})
    return out


class PlattCalibrator:
    """Calibration de Platt : p_cal = sigmoid(a·score + b), ajustée par descente de gradient."""

    def __init__(self, lr: float = 0.5, epochs: int = 500) -> None:
        self.a = 1.0
        self.b = 0.0
        self.lr = lr
        self.epochs = epochs

    def fit(self, scores, y) -> "PlattCalibrator":
        s = np.asarray(scores, dtype=float)
        t = np.asarray(y, dtype=float)
        if s.size == 0:
            return self
        # standardise les scores pour la stabilité
        mu, sd = float(s.mean()), float(s.std()) or 1.0
        self._mu, self._sd = mu, sd
        z = (s - mu) / sd
        a, b, n = 1.0, 0.0, s.size
        for _ in range(self.epochs):
            p = 1.0 / (1.0 + np.exp(-(a * z + b)))
            ga = float(np.mean((p - t) * z))
            gb = float(np.mean(p - t))
            a -= self.lr * ga
            b -= self.lr * gb
        self.a, self.b = a, b
        return self

    def transform(self, scores):
        s = np.asarray(scores, dtype=float)
        mu = getattr(self, "_mu", 0.0)
        sd = getattr(self, "_sd", 1.0)
        z = (s - mu) / sd
        return 1.0 / (1.0 + np.exp(-(self.a * z + self.b)))
