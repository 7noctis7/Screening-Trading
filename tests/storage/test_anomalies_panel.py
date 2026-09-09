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
    echelle_par_actif,
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


def _panel_heterogene(t: int = 400, graine: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Un panneau MULTI-CLASSES parfaitement sain : forex, actions, cryptos.

    C'est le panneau réel du projet en miniature. Les trois classes ne bougent pas à la
    même échelle — 0,5 %, 1,5 % et 5 % par jour — et c'est précisément là que le
    détecteur se trompait.
    """
    g = np.random.default_rng(graine)
    colonnes, classes = [], []
    for nom, (n, vol) in {"forex": (30, 0.005), "action": (40, 0.015),
                          "crypto": (10, 0.050)}.items():
        for _ in range(n):
            colonnes.append(100.0 * np.exp(np.cumsum(g.normal(0, vol, t))))
            classes.append(nom)
    return np.column_stack(colonnes), np.array(classes)


def test_une_classe_volatile_saine_n_est_pas_signalee() -> None:
    """LE test qui a motivé la normalisation par actif.

    Sans elle, la médiane et le MAD du jour sont dictés par la classe la plus nombreuse,
    et une crypto qui vit sa journée ordinaire se retrouve à seize écarts de cette
    coupe-là : signalée pour avoir été elle-même. Mesuré sur 774 séries SANS le moindre
    défaut injecté : 100 % des cryptos flaguées, 0 % du forex.

    Le contrôle porte sur la comparaison des deux modes, pas sur un chiffre absolu :
    l'ancien mode DOIT crier ici, sinon le test ne prouve rien.
    """
    p, classes = _panel_heterogene()
    r = np.diff(p, axis=0) / p[:-1]
    cryptos = set(np.where(classes == "crypto")[0].tolist())

    avant = {s["actif_index"] for s in ecart_a_la_coupe(r, normaliser=False)}
    apres = {s["actif_index"] for s in ecart_a_la_coupe(r, normaliser=True)}

    assert avant & cryptos, "contrôle inopérant : l'ancien mode ne signalait rien"
    assert not apres, f"des séries saines restent signalées : {sorted(apres)}"


def test_la_normalisation_ne_perd_pas_les_vrais_defauts() -> None:
    """Contre-partie obligatoire du test précédent : se taire, c'est facile.

    Un split ×4 sur une série d'échelle ordinaire, et un tick erroné dans la classe la
    PLUS volatile — celle où le bruit propre pourrait le mieux le cacher — doivent
    ressortir tous les deux.
    """
    p, classes = _panel_heterogene()
    j_split = int(np.where(classes == "action")[0][0])
    j_tick = int(np.where(classes == "crypto")[0][1])
    p[200:, j_split] /= 4.0
    p[250, j_tick] *= 3.0

    touches = {s["actif_index"] for s in auditer_panel(p)["sauts_isoles"]}
    assert j_split in touches, "split ×4 perdu sur une série d'échelle ordinaire"
    assert j_tick in touches, "tick erroné perdu dans la classe la plus volatile"


def test_l_angle_mort_du_seuil_calibre_est_connu_et_borne() -> None:
    """Le prix EXACT du seuil de 24, écrit noir sur blanc plutôt que subi.

    Un split ×4 vaut −75 %. Rapporté à l'échelle propre d'une crypto qui bouge de 5 %
    par jour, cela ne fait plus que quinze unités : sous le seuil. C'est précisément la
    part de splits que la mesure sur panneau réel annonce manquée — 93 % retrouvés à 24
    contre 98 % à 16 — et le contrepoids était de faire tomber la lecture de 128 actifs
    à 45. Un angle mort mesuré et borné n'est pas un défaut ; un angle mort ignoré, si.

    Le test vérifie AUSSI que le défaut ressort à seuil plus bas : sinon il constaterait
    une cécité totale au lieu d'un arbitrage.
    """
    p, classes = _panel_heterogene()
    j = int(np.where(classes == "crypto")[0][0])
    p[200:, j] /= 4.0
    r = np.diff(p, axis=0) / p[:-1]

    a_24 = {s["actif_index"] for s in ecart_a_la_coupe(r, 24.0)}
    a_12 = {s["actif_index"] for s in ecart_a_la_coupe(r, 12.0)}
    assert j not in a_24, "l'angle mort documenté n'existe plus : rouvrir le calibrage"
    assert j in a_12, "cécité totale : le défaut ne sort à aucun seuil"


def test_la_gravite_se_lit_sur_le_rendement_reel() -> None:
    """« Split non ajusté » se décide à −30 % de COURS, pas à trente unités d'écart.

    La normalisation divise les rendements par l'échelle de chaque actif ; si le rapport
    publiait cette valeur normalisée, un −25 % de forex (cinquante écarts propres)
    serait annoncé « donnée cassée » et un −40 % de crypto passerait pour « valeur
    extrême ». Le classement, qui commande le geste de réparation, serait inversé.
    """
    p, classes = _panel_heterogene()
    j = int(np.where(classes == "forex")[0][0])
    p[300:, j] /= 4.0                      # −75 % : un split, pas une donnée cassée

    sauts = [s for s in auditer_panel(p)["sauts_isoles"] if s["actif_index"] == j]
    assert sauts, "le split n'est pas détecté"
    pire = min(sauts, key=lambda s: s["rendement"])
    assert pire["rendement"] == pytest.approx(-0.75, abs=0.02), pire["rendement"]
    assert pire["gravite"] == "split non ajusté ?", pire["gravite"]


def test_une_serie_figee_ne_fait_pas_diverger_la_division() -> None:
    """Échelle propre nulle : la colonne sort de la comparaison au lieu de produire des
    infinis. C'est `series_figees` qui la signale, avec le motif juste."""
    p, _ = _panel_heterogene()
    p[:, 5] = 100.0                        # immobile de bout en bout → échelle nulle

    assert echelle_par_actif(np.diff(p, axis=0) / p[:-1])[5] == 0.0
    rapport = auditer_panel(p)
    assert all(np.isfinite(s["ecarts_robustes"]) for s in rapport["sauts_isoles"])
    assert any(f["actif_index"] == 5 for f in rapport["series_figees"])
