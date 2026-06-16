"""Métriques de classification + score en CV PURGÉE (évaluation OOS honnête)."""

from __future__ import annotations

import numpy as np

from packages.ml.cv import PurgedKFold


def accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return float((y_true == y_pred).mean()) if len(y_true) else 0.0


def precision_recall(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float]:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return prec, rec


def purged_cv_score(model_factory, X: np.ndarray, y: np.ndarray,
                    t0: np.ndarray, t1: np.ndarray, n_splits: int = 5,
                    embargo_pct: float = 0.01) -> list[float]:
    """Accuracy OOS par fold, avec purge + embargo. `model_factory` = callable()->modèle."""
    cv = PurgedKFold(n_splits=n_splits, embargo_pct=embargo_pct)
    scores: list[float] = []
    for tr, te in cv.split(t0, t1):
        if len(tr) == 0 or len(te) == 0 or len(np.unique(y[tr])) < 2:
            continue
        m = model_factory().fit(X[tr], y[tr])
        scores.append(accuracy(y[te], m.predict(X[te])))
    return scores
