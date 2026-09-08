"""Attraper le possible-mais-absurde, que le contrôle ligne par ligne laisse passer.

L'audit existant vérifie chaque série SÉPARÉMENT et attrape l'impossible : prix négatif,
plus-haut sous le plus-bas, dates décroissantes. Il ne peut pas voir ce qui est
parfaitement légal isolément et ne tient pas une seconde une fois replacé parmi les
autres — un split non ajusté, un tick erroné, un flux figé.

Chaque test injecte UN défaut connu dans un panneau sain, et vérifie qu'il ressort. Le
contrôle négatif compte autant : sur un panneau propre, l'audit doit se taire. Un
détecteur qui crie tout le temps ne sert à rien — on apprend à l'ignorer, et il devient
pire qu'absent.
"""

from __future__ import annotations

import numpy as np
import pytest

from packages.storage.anomalies_panel import (
    auditer_panel,
    ecart_a_la_coupe,
    series_figees,
)


def _panel_sain(t: int = 120, n: int = 25, graine: int = 0) -> np.ndarray:
    """Marché plausible : un facteur commun plus du bruit propre à chaque actif."""
    g = np.random.default_rng(graine)
    commun = g.normal(0, 0.01, (t, 1))
    propre = g.normal(0, 0.012, (t, n))
    return 100.0 * np.exp(np.cumsum(commun + propre, axis=0))


def test_un_panneau_sain_ne_declenche_rien() -> None:
    """LE contrôle négatif. Un détecteur qui crie tout le temps devient invisible."""
    rapport = auditer_panel(_panel_sain())
    assert rapport["ok"], rapport["resume"]


def test_un_split_non_ajuste_est_attrape() -> None:
    """Le cours est divisé par quatre du jour au lendemain. Rien d'illégal ligne à
    ligne — mais le marché entier n'a pas bougé ce jour-là."""
    p = _panel_sain()
    p[60:, 3] /= 4.0
    rapport = auditer_panel(p)
    assert not rapport["ok"]
    assert any(s["actif_index"] == 3 and s["date_index"] == 59
               for s in rapport["sauts_isoles"]), rapport["resume"]


def test_un_tick_aberrant_est_attrape() -> None:
    """Un prix faux, aussitôt corrigé : il passe tous les contrôles de forme et
    fabrique une volatilité et une queue qui n'existent pas."""
    p = _panel_sain()
    p[45, 7] *= 3.0
    assert any(s["actif_index"] == 7 for s in auditer_panel(p)["sauts_isoles"])


def test_un_flux_fige_est_attrape() -> None:
    """Le cas le plus dangereux : un cours immobile n'a ni dispersion ni queue, donc il
    paraît sans risque à TOUS les optimiseurs et hériterait d'un poids indu."""
    p = _panel_sain()
    p[80:, 11] = p[79, 11]
    figees = auditer_panel(p)["series_figees"]
    assert any(f["actif_index"] == 11 for f in figees), "flux figé non détecté"


def test_un_jour_ferie_global_n_est_pas_une_anomalie() -> None:
    """Si TOUT le monde est immobile, c'est un jour férié, pas un flux mort. Le
    reprocher noierait les vraies alertes."""
    p = _panel_sain()
    for k in range(1, 9):
        p[50 + k] = p[50]
    assert not series_figees(p), "un jour férié global est signalé à tort"


def test_un_krach_general_ne_declenche_pas_tout_le_panneau() -> None:
    """Le jour où tout tombe de 12 %, aucun actif ne s'ÉCARTE du marché. Comparer à
    zéro plutôt qu'à la coupe du jour signalerait les 25 actifs d'un coup."""
    p = _panel_sain()
    p[70:] *= 0.88
    sauts = [s for s in auditer_panel(p)["sauts_isoles"] if s["date_index"] == 69]
    assert not sauts, f"le krach général est pris pour {len(sauts)} anomalies"


def test_la_mediane_resiste_a_quelques_valeurs_extremes() -> None:
    """Trois actifs déments ne doivent pas rendre les vingt-deux autres « anormaux ».
    C'est pour ça qu'on utilise la médiane et le MAD, pas la moyenne et l'écart-type."""
    p = _panel_sain()
    for j in (2, 5, 9):
        p[30, j] *= 5.0
    touches = {s["actif_index"] for s in auditer_panel(p)["sauts_isoles"]
               if s["date_index"] == 29}
    assert touches <= {2, 5, 9}, f"des actifs sains entraînés : {touches}"


def test_rien_n_est_corrige_automatiquement() -> None:
    """On SIGNALE, l'humain tranche. Corriger en silence des données de marché
    effacerait la trace de ce qui n'allait pas."""
    p = _panel_sain()
    avant = p.copy()
    auditer_panel(p)
    assert np.array_equal(p, avant), "l'audit a modifié les données"


def test_une_matrice_mal_formee_leve() -> None:
    with pytest.raises(ValueError):
        auditer_panel(np.zeros((2, 5)))
    with pytest.raises(ValueError):
        ecart_a_la_coupe(np.zeros(10))
