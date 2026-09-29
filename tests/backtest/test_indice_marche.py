"""QML-009 — l'indice des portes de régime et d'ampleur ne pèse pas les titres par leur PRIX.

`mkt` valait `A.mean(axis=0)` : la moyenne des cours BRUTS du panier. Un titre à 500 $ y
pesait vingt-cinq fois un titre à 20 $. Une chute de 30 % du titre à 20 $ passait inaperçue
(−1 % d'indice) ; une chute de 20 % du titre à 500 $ ouvrait presque seule la porte du
drawdown dur. Un indice se construit sur des rendements, pas sur des niveaux.
"""

import numpy as np
import pytest


def _deux_titres(chute_cher: float, chute_bon_marche: float, n: int = 60):
    cher = np.full(n, 500.0)
    bon = np.full(n, 20.0)
    cher[30:] *= 1 + chute_cher
    bon[30:] *= 1 + chute_bon_marche
    return np.vstack([cher, bon])


def test_indice_equipondere_en_rendements():
    from packages.backtest.preset_helpers import indice_marche
    m = indice_marche(_deux_titres(0.0, -0.30))
    assert m[0] == pytest.approx(1.0)
    assert m[-1] / m.max() - 1 == pytest.approx(-0.15)      # moyenne des rendements


def test_le_prix_d_un_titre_ne_lui_donne_aucun_poids():
    from packages.backtest.preset_helpers import indice_marche
    a = indice_marche(_deux_titres(-0.20, 0.0))
    b = indice_marche(_deux_titres(0.0, -0.20))
    assert a[-1] == pytest.approx(b[-1])


def test_nan_titre_pas_encore_cote():
    from packages.backtest.preset_helpers import indice_marche
    A = _deux_titres(0.0, 0.0)
    A[1, :10] = np.nan                                      # introduit à la 11ᵉ séance
    A[1, 10:] *= np.linspace(1.0, 1.5, A.shape[1] - 10)
    m = indice_marche(A)
    assert np.all(np.isfinite(m)) and m[9] == pytest.approx(1.0)
