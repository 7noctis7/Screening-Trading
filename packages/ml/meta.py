"""Meta-labeling (López de Prado) — un 2ᵉ modèle décide d'AGIR ou non sur le signal primaire.

Le modèle primaire donne une direction ; le **méta-modèle** filtre les faux positifs (apprend
« quand le primaire a raison ») → améliore la **précision** au prix d'un peu de rappel. Mesuré sur
un jeu test indépendant. Numpy pur (le méta-modèle est fourni par l'appelant).
"""

from __future__ import annotations

import numpy as np


def meta_labels(primary_proba, y_true, thr: float = 0.5) -> np.ndarray:
    """Étiquette méta = 1 si la prédiction primaire (proba>thr → 1) est correcte."""
    pred = (np.asarray(primary_proba) > thr).astype(float)
    return (pred == np.asarray(y_true, dtype=float)).astype(float)


def _precision(pred_mask: np.ndarray, y: np.ndarray) -> tuple[float, int]:
    """Précision des positions « long » prédites (pred=1) + nombre de signaux."""
    sig = pred_mask.astype(bool)
    n = int(sig.sum())
    if n == 0:
        return 0.0, 0
    return round(float(y[sig].mean()), 3), n


def evaluate(primary_proba_test, meta_proba_test, y_test,
             p_thr: float = 0.5, m_thr: float = 0.5) -> dict:
    """Compare précision du primaire seul vs primaire filtré par le méta-modèle."""
    pp = np.asarray(primary_proba_test, dtype=float)
    mp = np.asarray(meta_proba_test, dtype=float)
    y = np.asarray(y_test, dtype=float)
    primary_long = pp > p_thr
    prec_p, n_p = _precision(primary_long, y)
    prec_m, n_m = _precision(primary_long & (mp > m_thr), y)
    return {"precision_primary": prec_p, "signals_primary": n_p,
            "precision_meta": prec_m, "signals_meta": n_m,
            "precision_gain": round(prec_m - prec_p, 3)}
