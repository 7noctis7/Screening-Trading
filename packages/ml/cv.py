"""Validation croisée PURGÉE & avec EMBARGO (López de Prado, AFML ch. 7).

En finance, les labels se CHEVAUCHENT dans le temps (un label couvre [t0, t1]). Une CV
naïve fuit : des échantillons d'entraînement chevauchant la fenêtre de test partagent de
l'information. On PURGE ces échantillons, et on ajoute un EMBARGO
(zone morte après le test)
pour neutraliser l'autocorrélation sérielle. Sans ça, les scores OOS sont illusoires.
"""

from __future__ import annotations

import numpy as np


class PurgedKFold:
    def __init__(
        self, n_splits: int = 5, embargo_pct: float = 0.01, label_horizon: int = 0
    ) -> None:
        if n_splits < 2:
            raise ValueError("n_splits >= 2")
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct
        if embargo_pct < 0 or label_horizon < 0:
            raise ValueError(
                "embargo et horizon de labellisation doivent être positifs"
            )
        self.label_horizon = int(label_horizon)

    def split(self, t0: np.ndarray, t1: np.ndarray):
        """`t0[i]`/`t1[i]` = indices (temps) de début/fin du label de l'échantillon i.

        Rend des paires (train_idx, test_idx) — positions d'échantillons.
        """
        t0 = np.asarray(t0)
        t1 = np.asarray(t1)
        n = len(t0)
        span = int(t1.max()) - int(t0.min()) + 1
        # Le pourcentage seul pouvait être inférieur à la triple barrière.
        # Le contrat dur est embargo >= horizon de labellisation.
        embargo = max(int(np.ceil(span * self.embargo_pct)), self.label_horizon)
        indices = np.arange(n)
        for test_idx in np.array_split(indices, self.n_splits):
            if len(test_idx) == 0:
                continue
            test_t0 = t0[test_idx].min()
            test_t1 = t1[test_idx].max() + embargo
            # purge : on retire tout échantillon train dont [t0,t1] chevauche le test
            overlap = (t1 >= test_t0) & (t0 <= test_t1)
            train_idx = indices[~overlap]
            train_idx = train_idx[~np.isin(train_idx, test_idx)]
            yield train_idx, test_idx
