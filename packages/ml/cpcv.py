"""Validation croisée COMBINATOIRE purgée avec embargo (López de Prado, AFML ch. 12).

`cv.PurgedKFold` produit UN seul chemin de backtest : k plis, une seule séquence
temporelle. On mesure alors une performance hors échantillon, mais pas sa DISPERSION —
or c'est la dispersion qui dit si le résultat tient. La CPCV teste `k_test` groupes parmi
`n_groups` à chaque fois, ce qui donne

    C(n_groups, k_test) découpages   →   phi = C(n_groups, k_test) · k_test / n_groups
                                          CHEMINS de backtest reconstitués

Avec n=6 et k=2 : 15 découpages, 5 chemins. On obtient une DISTRIBUTION de Sharpe hors
échantillon, seule base honnête pour le PBO et le Sharpe déflaté.

Purge et embargo sont conservés à l'identique : tout échantillon d'entraînement dont le
label [t0, t1] chevauche une fenêtre de test (élargie de l'embargo) est retiré.

⚠️ La CPCV multiplie les entraînements par C(n,k) : sur les robots 1 h, mesurer le coût
avant de choisir n_groups. numpy pur.
"""

from __future__ import annotations

from itertools import combinations
from math import comb

import numpy as np


def n_paths(n_groups: int, k_test: int) -> int:
    """Nombre de chemins de backtest reconstituables : C(n, k) · k / n."""
    if n_groups < 2 or not (1 <= k_test < n_groups):
        return 0
    return comb(n_groups, k_test) * k_test // n_groups


class CombinatorialPurgedCV:
    """Découpages combinatoires purgés. `split(t0, t1)` rend (train, test, groupes testés)."""

    def __init__(self, n_groups: int = 6, k_test: int = 2, embargo_pct: float = 0.01) -> None:
        if n_groups < 2:
            raise ValueError("n_groups >= 2")
        if not 1 <= k_test < n_groups:
            raise ValueError("1 <= k_test < n_groups")
        self.n_groups = n_groups
        self.k_test = k_test
        self.embargo_pct = embargo_pct

    @property
    def n_splits(self) -> int:
        return comb(self.n_groups, self.k_test)

    @property
    def n_paths(self) -> int:
        return n_paths(self.n_groups, self.k_test)

    def split(self, t0, t1):
        """`t0[i]`/`t1[i]` = début/fin (en index temporel) du label de l'échantillon i.

        Les échantillons DOIVENT être triés par t0 croissant : les groupes sont des blocs
        contigus dans le temps, sinon la purge ne protège rien.
        """
        a0 = np.asarray(t0)
        a1 = np.asarray(t1)
        n = len(a0)
        if n < self.n_groups:
            raise ValueError("moins d'échantillons que de groupes")
        if np.any(np.diff(a0) < 0):
            raise ValueError("échantillons non triés par t0 : la purge serait illusoire")
        idx = np.arange(n)
        groups = np.array_split(idx, self.n_groups)
        span = int(a1.max()) - int(a0.min()) + 1
        embargo = int(span * self.embargo_pct)
        for combo in combinations(range(self.n_groups), self.k_test):
            test_idx = np.concatenate([groups[g] for g in combo])
            keep = np.ones(n, dtype=bool)
            for g in combo:                      # purge fenêtre par fenêtre (groupes disjoints)
                g0 = a0[groups[g]].min()
                g1 = a1[groups[g]].max() + embargo
                keep &= ~((a1 >= g0) & (a0 <= g1))
            keep[test_idx] = False
            yield idx[keep], np.sort(test_idx), combo


def path_assignments(n_groups: int, k_test: int) -> list[list[tuple[int, int]]]:
    """Répartit les prédictions en `phi` chemins complets couvrant tous les groupes.

    Chaque groupe est testé dans C(n−1, k−1) découpages ; on distribue ces occurrences en
    phi chemins, chacun contenant exactement une prédiction par groupe. Renvoie, par chemin,
    la liste (groupe, index du découpage qui fournit la prédiction).
    """
    combos = list(combinations(range(n_groups), k_test))
    used: dict[int, list[int]] = {g: [s for s, c in enumerate(combos) if g in c]
                                  for g in range(n_groups)}
    phi = n_paths(n_groups, k_test)
    return [[(g, used[g][p]) for g in range(n_groups)] for p in range(phi)]
