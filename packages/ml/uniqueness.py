"""Unicité des échantillons et pondérations (López de Prado, AFML ch. 4).

Avec des labels à barrière temporelle, deux échantillons voisins couvrent presque le même
intervalle : ils portent la MÊME information. Les traiter comme indépendants gonfle la
taille effective de l'échantillon, donc la confiance — c'est la version « apprentissage »
du sur-comptage de souffle de l'axe 2.

Trois objets :
  - concurrence c(t) : nombre de labels actifs à la barre t ;
  - unicité moyenne d'un échantillon : moyenne de 1/c(t) sur son intervalle ;
  - poids d'échantillon : attribution du rendement, |somme des r(t)/c(t)|, normalisée.

L'unicité moyenne sert aussi à dimensionner un bagging honnête : tirer `max_samples` égal
à l'unicité moyenne évite qu'un arbre voie dix copies de la même information.
"""

from __future__ import annotations

import numpy as np


def concurrency(t0, t1, n_bars: int | None = None) -> np.ndarray:
    """Nombre de labels actifs à chaque barre (bornes incluses)."""
    a0 = np.asarray(t0, dtype=int)
    a1 = np.asarray(t1, dtype=int)
    if a0.size == 0:
        return np.zeros(0, dtype=float)
    n = int(n_bars if n_bars is not None else a1.max() + 1)
    counts = np.zeros(n + 1, dtype=float)
    np.add.at(counts, a0, 1.0)                     # différences finies : O(n + m)
    np.add.at(counts, np.minimum(a1 + 1, n), -1.0)
    return np.cumsum(counts)[:n]


def average_uniqueness(t0, t1, n_bars: int | None = None) -> np.ndarray:
    """Unicité moyenne par échantillon ∈ (0, 1]. 1 = aucun chevauchement."""
    a0 = np.asarray(t0, dtype=int)
    a1 = np.asarray(t1, dtype=int)
    c = concurrency(a0, a1, n_bars)
    inv = np.divide(1.0, c, out=np.zeros_like(c), where=c > 0)
    return np.array([float(inv[i0:i1 + 1].mean()) if i1 >= i0 else 0.0
                     for i0, i1 in zip(a0, a1)], dtype=float)


def return_attribution_weights(t0, t1, bar_returns, n_bars: int | None = None) -> np.ndarray:
    """Poids ∝ |somme sur l'intervalle de r(t)/c(t)|, normalisés à une moyenne de 1.

    Un label qui couvre une période calme et partagée pèse moins qu'un label qui capte
    seul un mouvement franc. C'est la pondération qui empêche le modèle d'optimiser le bruit.
    """
    a0 = np.asarray(t0, dtype=int)
    a1 = np.asarray(t1, dtype=int)
    r = np.asarray(bar_returns, dtype=float)
    c = concurrency(a0, a1, n_bars if n_bars is not None else len(r))
    m = min(len(r), len(c))
    contrib = np.zeros(m)
    np.divide(r[:m], c[:m], out=contrib, where=c[:m] > 0)
    cum = np.concatenate([[0.0], np.cumsum(contrib)])
    w = np.array([abs(cum[min(i1 + 1, m)] - cum[min(i0, m)]) for i0, i1 in zip(a0, a1)])
    s = w.sum()
    return w * (len(w) / s) if s > 0 else np.ones(len(w))


def time_decay_weights(avg_uniq, last_weight: float = 1.0) -> np.ndarray:
    """Décroissance LINÉAIRE en temps d'unicité cumulé (AFML 4.5).

    `last_weight` = poids de l'observation la PLUS ANCIENNE : 1 = pas de décroissance,
    0 = l'observation la plus ancienne ne compte plus, négatif = les plus anciennes sont
    purement et simplement écartées (utile après un changement de régime documenté).
    """
    u = np.asarray(avg_uniq, dtype=float)
    if u.size == 0:
        return u
    cum = np.cumsum(u[::-1])[::-1]                 # temps d'unicité restant, du récent au vieux
    cum = cum[::-1]                                # cumul croissant du plus ancien au plus récent
    total = cum[-1] if cum[-1] > 0 else 1.0
    c = last_weight
    slope = ((1.0 - c) / total) if c >= 0 else (1.0 / ((c + 1) * total))
    const = 1.0 - slope * total
    w = const + slope * cum
    return np.clip(w, 0.0, None)


def effective_sample_size(avg_uniq) -> float:
    """Taille d'échantillon EFFECTIVE = somme des unicités moyennes.

    C'est le n à utiliser dans tout test de significativité, jamais le nombre de lignes.
    """
    u = np.asarray(avg_uniq, dtype=float)
    return float(u.sum())
