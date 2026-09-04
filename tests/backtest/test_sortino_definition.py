"""Sortino : la déviation baissière se divise par N, pas par le nombre de pertes.

Constaté le 03/09 en comparant deux tableaux de la MÊME page du dashboard : Sortino
1,29 d'un côté, 1,82 de l'autre, sur des courbes dont les Sharpe différaient de 0,01.
Trois conventions coexistaient. Ce test vérifie la DÉFINITION, pas l'accord entre deux
implémentations — deux implémentations peuvent être d'accord et fausses ensemble.

LE SYMPTÔME À RETENIR : un Sortino INFÉRIEUR au Sharpe. Sauf asymétrie franchement
négative, la déviation baissière est plus petite que l'écart-type total, donc le Sortino
est plus GRAND. L'inverse signale presque toujours un dénominateur mal normalisé.
"""

import numpy as np

from packages.backtest.index_core import _stats


def _courbe(r) -> list[float]:
    return (100.0 * np.cumprod(1.0 + np.asarray(r, float))).tolist()


def _sortino_reference(r) -> float:
    """Définition : moyenne / racine de la moyenne SUR TOUT N des min(r,0)²."""
    r = np.asarray(r, float)
    dd = float((np.minimum(r, 0.0) ** 2).mean() ** 0.5)
    return float(r.mean() / dd * np.sqrt(252)) if dd > 0 else 0.0


def test_sortino_suit_la_definition_et_non_le_compte_des_pertes():
    rng = np.random.default_rng(7)
    r = rng.standard_t(df=4, size=2400) * 0.009 + 0.0007
    st = _stats(_courbe(r))
    assert abs(st["sortino"] - round(_sortino_reference(r), 2)) < 0.01


def test_diviser_par_le_nombre_de_pertes_ecrase_le_ratio():
    """L'ancienne formule, reproduite ici : l'écart est CHIFFRÉ, pas décrit."""
    rng = np.random.default_rng(7)
    r = rng.standard_t(df=4, size=2400) * 0.009 + 0.0007
    dn = r[r < 0]
    ancienne = float(r.mean() / (dn ** 2).mean() ** 0.5 * np.sqrt(252))
    correcte = _sortino_reference(r)
    assert ancienne < correcte
    assert 0.65 < ancienne / correcte < 0.75          # ~30 % trop bas


def test_sortino_depasse_le_sharpe_sur_une_serie_a_asymetrie_positive():
    """Contrôle de bon sens : plus de hausses extrêmes que de baisses."""
    rng = np.random.default_rng(3)
    r = np.abs(rng.normal(0, 0.012, 3000)) - 0.006     # queue droite épaisse
    st = _stats(_courbe(r))
    assert st["sortino"] > st["sharpe"]


def test_aucune_perte_ne_donne_pas_un_ratio_infini():
    st = _stats(_courbe([0.001] * 300))
    assert st["sortino"] == 0.0            # dénominateur nul → 0, jamais inf
