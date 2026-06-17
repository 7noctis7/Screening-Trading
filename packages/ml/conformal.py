"""Conformal prediction (split/LAC) — garanties de couverture distribution-free.

Best practice ML moderne (MAPIE/López de Prado) : au lieu d'une proba ponctuelle, produire un
**ensemble de prédiction** avec une couverture garantie (1−α) sous échangeabilité. Pour la
classification binaire, on calibre un seuil de non-conformité et on en déduit, par point, un
ensemble ⊆ {0,1}. Numpy pur, testable hors-ligne.
"""

from __future__ import annotations

import numpy as np


def calibrate_threshold(p_cal, y_cal, alpha: float = 0.1) -> float:
    """Seuil de non-conformité q̂ (LAC) au niveau 1−α à partir d'un jeu de calibration.

    Non-conformité s = 1 − p(classe vraie). q̂ = quantile ⌈(n+1)(1−α)⌉/n des s.
    """
    p = np.clip(np.asarray(p_cal, dtype=float), 0.0, 1.0)
    y = np.asarray(y_cal, dtype=float)
    if p.size == 0:
        return 1.0
    s = np.where(y >= 0.5, 1.0 - p, p)          # 1 − proba de la vraie classe
    n = s.size
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(s, level, method="higher"))


def prediction_sets(p_test, qhat: float) -> list[list[int]]:
    """Ensemble {0/1} par point : classe c incluse si (1 − p_c) ≤ q̂."""
    p = np.clip(np.asarray(p_test, dtype=float), 0.0, 1.0)
    out: list[list[int]] = []
    for pi in p:
        s = []
        if (1.0 - pi) <= qhat:      # classe 1
            s.append(1)
        if pi <= qhat:              # classe 0  (1 − p_0 = p)
            s.append(0)
        out.append(s or [int(pi >= 0.5)])   # jamais vide (repli sur l'argmax)
    return out


def evaluate(p_cal, y_cal, p_test, y_test, alpha: float = 0.1) -> dict:
    """Couverture empirique + taille moyenne d'ensemble sur un jeu test."""
    qhat = calibrate_threshold(p_cal, y_cal, alpha)
    sets = prediction_sets(p_test, qhat)
    y = np.asarray(y_test, dtype=float)
    covered = sum(1 for st, yi in zip(sets, y) if int(round(yi)) in st)
    n = len(sets) or 1
    return {"target_coverage": round(1 - alpha, 3),
            "empirical_coverage": round(covered / n, 3),
            "avg_set_size": round(sum(len(s) for s in sets) / n, 3),
            "qhat": round(qhat, 4)}
