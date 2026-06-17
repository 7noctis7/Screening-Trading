"""Walk-forward — validation hors-échantillon glissante (best practice anti-surapprentissage).

On entraîne sur le passé, on teste sur le futur immédiat, puis on glisse. Deux modes :
**ancré** (train grandit) ou **glissant** (fenêtre fixe). Renvoie des plages d'indices (sur des
données déjà triées par le temps). stdlib pur, testable.
"""

from __future__ import annotations


def walk_forward_splits(n: int, n_splits: int = 5, train_frac: float = 0.5,
                        anchored: bool = True) -> list[tuple[range, range]]:
    """Génère (train, test) sur n points triés temporellement.

    Args:
        n: nombre d'échantillons.
        n_splits: nombre de plis hors-échantillon.
        train_frac: part initiale d'entraînement.
        anchored: True = train ancré (grandit) ; False = fenêtre glissante de taille fixe.
    """
    if n < 4 or n_splits < 1:
        return []
    start_train = max(1, int(n * train_frac))
    test_size = max(1, (n - start_train) // n_splits)
    if test_size == 0:
        return []
    splits: list[tuple[range, range]] = []
    test_start = start_train
    while test_start < n and len(splits) < n_splits:
        test_end = min(n, test_start + test_size)
        train_start = 0 if anchored else max(0, test_start - start_train)
        if test_end - test_start < 1 or test_start - train_start < 1:
            break
        splits.append((range(train_start, test_start), range(test_start, test_end)))
        test_start = test_end
    return splits
