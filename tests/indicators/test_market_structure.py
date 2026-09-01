"""Structure de marché (spec utilisateur 01/09, module 1).

Le test qui compte le plus n'est aucun des signaux : c'est le POINT-IN-TIME. Un
détecteur de structure qui lit une barre future produit un backtest magnifique et
inexploitable. On le vérifie mécaniquement, pas par relecture.
"""

from dataclasses import dataclass

import pytest

from packages.indicators import market_structure as ms


@dataclass
class B:
    open: float
    high: float
    low: float
    close: float
    volume: float


def _plates(n: int, prix: float = 100.0, vol: float = 1_000.0) -> list:
    return [B(prix, prix + 0.5, prix - 0.5, prix, vol) for _ in range(n)]


def _zigzag(n: int, pente: float, base: float = 100.0, ampl: float = 4.0,
            periode: int = 12) -> list:
    """Tendance RÉALISTE : une dérive plus des oscillations.

    Une série strictement monotone n'a AUCUN pivot — chaque barre est dépassée par la
    suivante, donc aucun sommet local n'existe. `tendance` la classe « range », et
    c'est correct : sans structure de swings, il n'y a pas de hauts/bas à comparer.
    Un vrai marché oscille ; le jeu d'essai doit le faire aussi.
    """
    import math
    out = []
    for k in range(n):
        c = base + pente * k + ampl * math.sin(2 * math.pi * k / periode)
        out.append(B(c, c + 1.0, c - 1.0, c, 1_000.0))
    return out


def test_le_module_demarre_en_SHADOW():
    assert ms.STATUT == "SHADOW_UNCALIBRATED"


# --------------------------------------------------------------- POINT-IN-TIME
def test_aucune_fonction_ne_lit_une_barre_FUTURE():
    """LE test. On calcule à l'indice i, puis on MODIFIE toutes les barres après i de
    façon extrême. Si un résultat change, la fonction lisait le futur."""
    barres = _plates(80)
    barres[60] = B(100, 101, 96, 100.8, 5_000)          # mèche basse + volume
    i = 60
    avant = (ms.bas_protege(barres, i).as_dict(), ms.haut_protege(barres, i).as_dict(),
             ms.echec_enchere(barres, i), ms.tendance(barres, i),
             round(ms.point_de_controle(barres, i), 6))
    for j in range(i + 1, len(barres)):                  # futur saccagé
        barres[j] = B(999, 9_999, 1, 9_998, 1e9)
    apres = (ms.bas_protege(barres, i).as_dict(), ms.haut_protege(barres, i).as_dict(),
             ms.echec_enchere(barres, i), ms.tendance(barres, i),
             round(ms.point_de_controle(barres, i), 6))
    assert avant == apres, "une fonction lit une barre postérieure à i"


# --------------------------------------------------------------- volume
def test_le_volume_de_reference_EXCLUT_la_barre_courante():
    """S'inclure dans sa propre moyenne la dilue, et rend le seuil plus facile à
    franchir quand le volume explose — l'inverse de ce qu'on veut détecter."""
    barres = _plates(40)
    barres[30] = B(100, 100.5, 99.5, 100, 1_000_000)
    assert ms.volume_exceptionnel(barres, 30)


def test_volume_plat_nest_pas_exceptionnel():
    assert not ms.volume_exceptionnel(_plates(40), 30)


def test_volume_en_debut_de_serie_ne_plante_pas():
    assert ms.volume_exceptionnel(_plates(40), 0) is False


# --------------------------------------------------------------- extrêmes
def test_bas_protege_exige_meche_ET_volume():
    barres = _plates(40)
    barres[30] = B(100, 100.2, 96.0, 100.0, 5_000)       # mèche basse ~95 %
    assert ms.bas_protege(barres, 30).protege
    barres[30] = B(100, 100.2, 96.0, 100.0, 1_000)       # même mèche, volume normal
    assert not ms.bas_protege(barres, 30).protege, "le volume doit être exigé"


def test_une_grande_meche_sans_volume_ne_suffit_PAS():
    barres = _plates(40)
    barres[30] = B(100, 100.1, 90.0, 100.0, 900)
    e = ms.bas_protege(barres, 30)
    assert e.part_meche > 0.9 and not e.volume_fort and not e.protege


def test_haut_protege_est_symetrique():
    barres = _plates(40)
    barres[30] = B(100, 104.0, 99.9, 100.0, 5_000)
    assert ms.haut_protege(barres, 30).protege


def test_bougie_plate_ne_divise_pas_par_zero():
    barres = _plates(40)
    barres[30] = B(100, 100, 100, 100, 5_000)
    assert ms.bas_protege(barres, 30).part_meche == 0.0


# --------------------------------------------------------------- tendance
def test_tendance_haussiere_detectee():
    assert ms.tendance(_zigzag(80, pente=+0.8), 79) == "haussier"


def test_tendance_baissiere_detectee():
    assert ms.tendance(_zigzag(80, pente=-0.8, base=200.0), 79) == "baissier"


def test_marche_plat_classe_en_RANGE():
    assert ms.tendance(_plates(80), 79) == "range"


def test_une_serie_MONOTONE_est_classee_range_et_c_est_correct():
    """Sans oscillation il n'existe aucun pivot : pas de hauts/bas à comparer, donc
    pas de structure. Répondre « haussier » sur une droite serait deviner."""
    droite = [B(100 + k, 101 + k, 99 + k, 100.5 + k, 1_000) for k in range(80)]
    assert ms.tendance(droite, 79) == "range"


def test_historique_trop_court_rend_range():
    assert ms.tendance(_plates(10), 9) == "range"


# --------------------------------------------------------------- confluence
def test_aucune_entree_si_le_HTF_est_en_RANGE():
    """Le filtre qui supprime le plus de trades — et sur une stratégie à l'équilibre,
    supprimer des trades est le levier le plus fiable."""
    ltf = _plates(40)
    ltf[30] = B(100, 100.2, 96.0, 100.0, 5_000)
    r = ms.confluence(_plates(80), 79, ltf, 30)
    assert not r["autorise"] and "range" in r["motif"]


def test_long_autorise_en_tendance_haussiere_avec_bas_protege():
    htf = _zigzag(80, pente=+0.8)
    ltf = _plates(60)
    ltf[50] = B(100, 100.2, 96.0, 100.0, 9_000)
    r = ms.confluence(htf, 79, ltf, 50)
    assert r["autorise"] and r["sens"] == "long"


def test_pas_de_LONG_en_tendance_BAISSIERE():
    """Le sens du HTF commande : un bas protégé en tendance baissière ne suffit pas."""
    htf = _zigzag(80, pente=-0.8, base=200.0)
    ltf = _plates(60)
    ltf[50] = B(100, 100.2, 96.0, 100.0, 9_000)
    assert not ms.confluence(htf, 79, ltf, 50)["autorise"]


# --------------------------------------------------------------- POC
def test_le_POC_tombe_dans_la_plage_des_prix():
    barres = _plates(80)
    poc = ms.point_de_controle(barres, 79)
    assert min(b.low for b in barres) <= poc <= max(b.high for b in barres)


def test_le_POC_suit_le_volume():
    barres = _plates(80, prix=100.0)
    for k in range(70, 80):
        barres[k] = B(120, 120.5, 119.5, 120, 500_000)
    assert ms.point_de_controle(barres, 79) > 110


def test_POC_sur_serie_trop_courte_rend_le_dernier_cours():
    barres = _plates(3)
    assert ms.point_de_controle(barres, 2) == pytest.approx(barres[2].close)
