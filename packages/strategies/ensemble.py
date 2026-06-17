"""Ensemble de stratégies — combine plusieurs signaux en un (best practice multi-stratégie).

Diversifier les sources d'alpha réduit la variance du signal. On combine des signaux normalisés
(∈ [-1, 1]) par moyenne pondérée, puis on applique un seuil pour décider long/flat/short. Pur.
"""

from __future__ import annotations


def combine_signals(signals: dict[str, list[float]],
                    weights: dict[str, float] | None = None) -> list[float]:
    """Moyenne pondérée de signaux alignés (même longueur). Poids égaux par défaut."""
    if not signals:
        return []
    names = list(signals)
    n = min(len(signals[k]) for k in names)
    w = weights or {k: 1.0 for k in names}
    tot = sum(w.get(k, 0.0) for k in names) or 1.0
    out = []
    for i in range(n):
        out.append(round(sum(w.get(k, 0.0) * signals[k][i] for k in names) / tot, 6))
    return out


def discretize(combined: list[float], threshold: float = 0.2) -> list[int]:
    """Signal continu → position discrète {-1, 0, +1} via une bande morte (réduit le bruit)."""
    return [1 if x > threshold else (-1 if x < -threshold else 0) for x in combined]
