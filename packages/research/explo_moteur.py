"""Moteur minimal du banc d'exploration : décision au close t, exécution au close t+lag.

Volontairement plus simple que le rejeu de production (`preset_rejeu`) : pas de bande, pas
de plancher d'ordre, pas de portail. Il sert à CLASSER des règles entre elles à coûts
identiques, pas à prédire ce que la production aurait gagné. Les frais sont appliqués au
turnover mesuré contre les poids DÉTENUS (dérivés avec les prix), jamais contre la cible
précédente (QML-013).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from packages.backtest.preset_core import deriver


def _rendements_barres(A: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        r = A[:, 1:] / A[:, :-1] - 1.0
    return np.where(np.isfinite(r), r, 0.0)            # pas de prix = pas de rendement


def simuler(A: np.ndarray, poids_fn: Callable[[int], np.ndarray], pas: int,
            couts: np.ndarray, debut: int, fin: int, lag: int = 1) -> dict:
    """Rendements nets des barres debut→debut+1 … fin-1→fin.

    `poids_fn(t)` ne doit lire que les barres ≤ t (cf. `explo_regles`). Une décision dont
    l'exécution tomberait à `fin` ou au-delà n'est pas prise : elle ne produirait aucun
    rendement, seulement des frais."""
    A = np.asarray(A, float)
    R = _rendements_barres(A)
    couts = np.asarray(couts, float)
    tenu = np.zeros(A.shape[0])
    en_attente: dict[int, np.ndarray] = {}
    out, frais, turnover, n_exec = [], 0.0, 0.0, 0
    for t in range(debut, fin):
        cout_t = 0.0
        if t in en_attente:
            cible = en_attente.pop(t)
            delta = np.abs(cible - tenu)
            cout_t = float((delta * couts).sum())
            frais += cout_t
            turnover += float(delta.sum())
            tenu, n_exec = cible, n_exec + 1
        if (t - debut) % max(1, pas) == 0 and t + lag < fin:
            en_attente[t + lag] = np.asarray(poids_fn(t), float)
        r = R[:, t]                                    # barre t → t+1
        out.append(float((tenu * r).sum()) - cout_t)
        tenu = deriver(tenu, r)
    return {"rendements": np.asarray(out), "frais": frais, "turnover": turnover,
            "n_executions": n_exec}
