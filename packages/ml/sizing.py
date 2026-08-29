"""Sizing de position piloté par la confiance (López de Prado : bet sizing).

La taille reflète la **conviction** : edge du modèle primaire × confiance du
méta-modèle. On compare une mise dimensionnée à une mise binaire sur un jeu test.
Numpy pur, testable hors-ligne.
"""

from __future__ import annotations

import numpy as np


def bet_size(primary_proba, meta_proba=None, max_size: float = 1.0):
    """Taille ∈ [-max,+max] : edge=(2p−1) pondéré par la confiance méta (sinon 1)."""
    p = np.clip(np.asarray(primary_proba, dtype=float), 0.0, 1.0)
    edge = 2.0 * p - 1.0
    conf = (
        np.clip(np.asarray(meta_proba, dtype=float), 0.0, 1.0)
        if meta_proba is not None
        else 1.0
    )
    return np.clip(edge * conf, -max_size, max_size)


def evaluate_sizing(primary_proba, y, meta_proba=None) -> dict:
    """Compare le P&L (en unités de label ±1) d'une mise dimensionnée vs binaire.

    outcome = 2y−1 et pnl = taille × outcome. On rapporte le P&L moyen
    et un ratio d'information (moyenne/écart-type) pour chaque approche.
    """
    p = np.clip(np.asarray(primary_proba, dtype=float), 0.0, 1.0)
    y = np.asarray(y, dtype=float)
    if p.size == 0:
        return {"available": False}
    outcome = 2.0 * y - 1.0
    size = bet_size(p, meta_proba)
    naive = np.sign(2.0 * p - 1.0)
    pnl_s, pnl_n = size * outcome, naive * outcome

    def _ir(x):
        sd = x.std()
        return round(float(x.mean() / sd), 3) if sd > 0 else 0.0

    return {
        "available": True,
        "avg_size": round(float(np.abs(size).mean()), 3),
        "pnl_sized": round(float(pnl_s.mean()), 4),
        "pnl_naive": round(float(pnl_n.mean()), 4),
        "ir_sized": _ir(pnl_s),
        "ir_naive": _ir(pnl_n),
        "uplift": round(float(pnl_s.mean() - pnl_n.mean()), 4),
    }


def conformal_weight(
    target_weight: float, confidence: float, max_uncertainty: float
) -> float:
    """Réduit un poids par confiance conforme ; au-delà du mandat, force zéro.

    ``confidence`` est dans [0, 1] et ``uncertainty = 1 - confidence``. Cette fonction
    ne peut donc jamais augmenter la cible amont.
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence doit appartenir à [0, 1]")
    if not 0.0 <= max_uncertainty <= 1.0:
        raise ValueError("max_uncertainty doit appartenir à [0, 1]")
    if 1.0 - confidence > max_uncertainty:
        return 0.0
    return float(target_weight) * confidence
