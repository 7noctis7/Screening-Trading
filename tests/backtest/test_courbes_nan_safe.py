"""Un cours manquant ne doit JAMAIS détruire une courbe de dix ans.

LA PANNE DU 04/09, telle qu'elle s'est présentée : le tableau de bord affichait
CAGR −100 %, gain total −100 %, pire baisse −100 % — avec un Sharpe de 0,25 et un
Sortino de 0,18, RESTÉS POSITIFS. Cette combinaison est arithmétiquement impossible pour
une vraie courbe : un capital réduit à zéro donne un Sharpe franchement négatif. C'est
elle qui a permis de remonter à la cause, parce que les deux familles de chiffres ne
sont pas calculées au même endroit — les ratios sur les rendements, le CAGR sur les
extrémités de la courbe nettoyée.

LE MÉCANISME : `0 * nan` vaut `nan` en numpy. Un titre au poids ZÉRO, qu'on ne détient
pas, suffisait à rendre le rendement du jour NaN dès qu'il lui manquait un cours ;
l'equity devenait NaN, puis toute la fin de la courbe. `dump_static._clean` convertit
NaN en `None`, que le front lit comme zéro.

Depuis l'alignement par date, la matrice CONTIENT légitimement des NaN — un titre ne
cote pas toutes les dates du panel. Le NaN n'est pas une anomalie à traquer en amont,
c'est un état normal que ces calculs doivent savoir traverser.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.megacap import _rendement_pondere
from packages.backtest.preset_curves import _rendement_du_jour


def test_zero_fois_nan_vaut_nan_en_numpy():
    """Le fait qui rendait le défaut discret : le titre fautif n'est pas détenu."""
    assert np.isnan(np.array([0.0]) * np.array([np.nan]))[0]


# ─────────────────────────── courbe du preset ───────────────────────────

def test_un_titre_NON_DETENU_sans_cours_ne_casse_plus_la_courbe():
    """Le cas exact de la production : poids nul, cours manquant, courbe détruite."""
    A = np.array([[100.0, 101.0], [50.0, 50.5], [10.0, np.nan]])
    w = np.array([0.5, 0.5, 0.0])
    r = _rendement_du_jour(A, w, 0)
    assert np.isfinite(r)
    assert abs(r - 0.01) < 1e-9        # les deux lignes détenues ont fait +1 %


def test_un_titre_DETENU_sans_cours_renormalise_les_poids():
    """Ignorer une ligne sans renormaliser supposerait qu'elle fait 0 % ce jour-là —
    un rendement inventé, pas une absence."""
    A = np.array([[100.0, 101.0], [50.0, np.nan], [10.0, 10.0]])
    r = _rendement_du_jour(A, np.array([0.5, 0.5, 0.0]), 0)
    assert abs(r - 0.01) < 1e-9        # +1 % de la seule ligne cotée, pas +0,5 %


def test_aucune_ligne_detenue_cotee_donne_ZERO_pas_NaN():
    """Zéro est le bon repli : on n'a rien pu mesurer, on ne perd rien."""
    A = np.array([[100.0, np.nan], [50.0, np.nan], [10.0, 10.0]])
    assert _rendement_du_jour(A, np.array([0.5, 0.5, 0.0]), 0) == 0.0


def test_un_cours_NUL_ne_produit_pas_un_rendement_infini():
    """Diviser par zéro donnerait ±inf, qui contamine aussi bien que NaN."""
    A = np.array([[0.0, 101.0], [50.0, 50.5]])
    r = _rendement_du_jour(A, np.array([0.5, 0.5]), 0)
    assert np.isfinite(r) and abs(r - 0.01) < 1e-9


def test_la_courbe_entiere_survit_a_un_trou():
    """Le test qui aurait attrapé la panne : une equity composée bout à bout."""
    A = np.array([[100.0, 101.0, np.nan, 102.0], [50.0, 50.5, 51.0, 51.5]])
    w = np.array([0.5, 0.5])
    eq = [10000.0]
    for t in range(A.shape[1] - 1):
        eq.append(eq[-1] * (1 + _rendement_du_jour(A, w, t)))
    assert all(np.isfinite(x) for x in eq)
    assert eq[-1] > eq[0]              # et elle n'est pas tombée à zéro


# ─────────────────────────── cœur megacap ───────────────────────────

def test_megacap_survit_aussi_a_un_trou():
    """Même défaut : `sector_momentum` portait déjà la garde, celui-ci non."""
    closes = {"A": np.array([100.0, 101.0, np.nan, 102.0]),
              "B": np.array([50.0, 50.5, 51.0, 51.5])}
    eq = [10000.0]
    for t in range(3):
        eq.append(eq[-1] * (1 + _rendement_pondere(closes, {"A": 0.5, "B": 0.5},
                                                   ["A", "B"], t)))
    assert all(np.isfinite(x) for x in eq)
    assert eq[-1] > eq[0]


def test_megacap_renormalise_lui_aussi():
    closes = {"A": np.array([100.0, np.nan]), "B": np.array([50.0, 50.5])}
    r = _rendement_pondere(closes, {"A": 0.5, "B": 0.5}, ["A", "B"], 0)
    assert abs(r - 0.01) < 1e-9


def test_megacap_sans_ligne_cotee_donne_zero():
    closes = {"A": np.array([100.0, np.nan]), "B": np.array([50.0, np.nan])}
    assert _rendement_pondere(closes, {"A": 0.5, "B": 0.5}, ["A", "B"], 0) == 0.0
