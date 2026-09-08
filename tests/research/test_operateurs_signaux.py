"""Aucun opérateur ne doit lire le futur — le reste vient après.

Un décalage d'UNE ligne dans le mauvais sens fabrique un signal spectaculaire et
parfaitement faux. Le piège est qu'il ne ressemble pas à un bug : les chiffres
deviennent justement très beaux, et c'est ce qui donne envie d'y croire. Aucun contrôle
statistique ne le rattrape ensuite — un IC de 0,4 obtenu en trichant passe toutes les
portes du gate.

D'où le test central de ce fichier, appliqué à CHAQUE opérateur temporel : on modifie
le futur et on exige que le passé ne bouge pas d'un iota. C'est la seule vérification
qui distingue structurellement une fenêtre glissante correcte d'une fenêtre décalée.

Le second garde-fou : les premières lignes valent NaN tant que la fenêtre n'est pas
pleine. Compléter par une moyenne ou un zéro contaminerait toute l'étude, et le ferait
silencieusement.
"""

from __future__ import annotations

import numpy as np
import pytest

from packages.research.operateurs_signaux import (
    FENETRES,
    OPERATEURS_TEMPORELS,
    OPERATEURS_TRANSVERSAUX,
)


def _panneau(t: int = 200, n: int = 12, graine: int = 0) -> dict:
    g = np.random.default_rng(graine)
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    return {
        "open": close * (1 + g.normal(0, 0.002, (t, n))),
        "high": close * (1 + np.abs(g.normal(0, 0.006, (t, n)))),
        "low": close * (1 - np.abs(g.normal(0, 0.006, (t, n)))),
        "close": close,
        "volume": np.abs(g.lognormal(10, 0.5, (t, n))),
    }


@pytest.mark.parametrize("nom_op", sorted(OPERATEURS_TEMPORELS))
def test_aucun_operateur_ne_lit_le_futur(nom_op: str) -> None:
    """LE test. On casse le futur ; le passé doit être identique au bit près."""
    p = _panneau()
    coupure = 150
    avant = OPERATEURS_TEMPORELS[nom_op](p, 21)[:coupure]

    saccage = {k: v.copy() for k, v in p.items()}
    for k in saccage:
        saccage[k][coupure:] *= 7.5          # le futur devient méconnaissable
    apres = OPERATEURS_TEMPORELS[nom_op](saccage, 21)[:coupure]

    assert np.allclose(avant, apres, equal_nan=True), (
        f"{nom_op} change de valeur AVANT la coupure quand on modifie APRÈS : il "
        "lit le futur. Tout signal construit dessus serait faux et flatteur."
    )


@pytest.mark.parametrize("nom_op", sorted(OPERATEURS_TEMPORELS))
def test_la_fenetre_incomplete_reste_vide(nom_op: str) -> None:
    """Pas de valeur inventée au démarrage : NaN tant que la fenêtre est
    incomplète."""
    sortie = OPERATEURS_TEMPORELS[nom_op](_panneau(), 21)
    assert np.isnan(sortie[0]).all(), (
        f"{nom_op} produit une valeur dès la première ligne, sans historique : "
        "elle est fabriquée."
    )


@pytest.mark.parametrize("nom_op", sorted(OPERATEURS_TEMPORELS))
def test_chaque_operateur_produit_de_la_variation(nom_op: str) -> None:
    """Contrôle négatif des deux tests précédents : un opérateur qui rendrait
    uniquement des NaN les passerait tous les deux sans rien calculer."""
    sortie = OPERATEURS_TEMPORELS[nom_op](_panneau(), 21)
    fini = sortie[np.isfinite(sortie)]
    assert fini.size > 100, f"{nom_op} ne produit presque rien"
    assert float(np.std(fini)) > 0, f"{nom_op} rend une constante"


def test_le_momentum_retrouve_une_hausse_connue() -> None:
    """Valeur vérifiable à la main : +10 % sur la fenêtre doit rendre +0,10."""
    t = 60
    close = np.ones((t, 1))
    close[30:] = 1.10
    p = {c: close.copy() for c in ("open", "high", "low", "close", "volume")}
    m = OPERATEURS_TEMPORELS["momentum"](p, 21)
    assert m[50, 0] == pytest.approx(0.10, abs=1e-9)


def test_la_position_dans_la_bande_est_bornee() -> None:
    """0 au plancher, 1 au sommet. Hors de [0, 1], la formule serait fausse."""
    sortie = OPERATEURS_TEMPORELS["position_dans_la_bande"](_panneau(), 21)
    fini = sortie[np.isfinite(sortie)]
    assert fini.min() >= -1e-9 and fini.max() <= 1 + 1e-9


def test_le_rang_transversal_compare_bien_les_actifs_entre_eux() -> None:
    """Le rang doit être calculé DATE PAR DATE. Sur toute l'histoire d'un actif, il
    utiliserait des valeurs qu'on ne connaîtra que plus tard."""
    x = np.array([[3.0, 1.0, 2.0], [1.0, 2.0, 3.0]])
    rangs = OPERATEURS_TRANSVERSAUX["rang"](x)
    assert rangs[0].tolist() == [1.0, 0.0, 0.5], "rang faux sur la première date"
    assert rangs[1].tolist() == [0.0, 0.5, 1.0], "rang faux sur la seconde date"


def test_le_zscore_transversal_est_calcule_par_date() -> None:
    """Même exigence : une date, une coupe. Deux dates de niveaux très différents
    doivent donner des z-scores comparables."""
    x = np.array([[1.0, 2.0, 3.0], [100.0, 200.0, 300.0]])
    z = OPERATEURS_TRANSVERSAUX["zscore"](x)
    assert np.allclose(z[0], z[1], atol=1e-6), (
        "le z-score mélange les dates : il utiliserait des moyennes venues du futur"
    )


def test_les_fenetres_proposees_sont_croissantes_et_plausibles() -> None:
    assert list(FENETRES) == sorted(FENETRES)
    assert FENETRES[0] >= 2 and FENETRES[-1] <= 252
