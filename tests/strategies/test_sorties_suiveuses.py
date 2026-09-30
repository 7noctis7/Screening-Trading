"""Stops suiveurs et prise de gains — la mathématique, avant toute mesure sur données réelles.

Deux règles de stop, une prise partielle, et trois invariants qui ne se négocient pas :
  1. le stop ne RECULE jamais (cliquet) ;
  2. l'état au close `d` ne lit que les barres ≤ d ; la barre d+1 ne sert qu'à constater
     le déclenchement d'un ordre déjà posé ;
  3. l'hypothèse défavorable l'emporte : gap sous le stop → exécution à l'ouverture ;
     stop et cible touchés dans la même barre → le stop.

L'ADR-0052 a mesuré qu'un suiveur ATR tronquait la queue droite de la stratégie swing :
ces tests valident le mécanisme, ils ne disent rien de son intérêt pour le portefeuille.
"""

from __future__ import annotations

import math

import pytest

from packages.strategies.sorties_suiveuses import (
    REGLES,
    Barre,
    Reglages,
    atr_initial,
    atr_suivant,
    avancer,
    declencher,
    ouvrir,
)

R3 = Reglages(periode_atr=3, pivot=2, fenetre=40)


def _plates(closes, amplitude=1.0):
    """Barres de range constant (TR = 2·amplitude quand les pas sont petits)."""
    return [Barre(c, c + amplitude, c - amplitude, c) for c in closes]


def _depuis_bas(bas, largeur=2.0):
    return [Barre(b + 1.0, b + largeur, b, b + 1.0) for b in bas]


# ------------------------------------------------------------------ ATR (Wilder)

def test_atr_initial_moyenne_des_vrais_ranges():
    barres = _plates([100.0, 100.5, 101.0, 101.5])
    assert atr_initial(barres, 3) == pytest.approx(2.0)


def test_atr_initial_insuffisant_est_nan():
    assert math.isnan(atr_initial(_plates([100.0, 101.0]), 3))


def test_atr_suivant_recurrence_de_wilder():
    assert atr_suivant(2.0, 5.0, 3) == pytest.approx((2.0 * 2 + 5.0) / 3)


# ------------------------------------------------------------------ ouverture

def test_ouverture_impossible_sans_atr():
    assert ouvrir("atr", _plates([100.0, 101.0]), 101.0, reglages=R3) is None


def test_regle_inconnue_refusee():
    with pytest.raises(ValueError):
        ouvrir("magique", _plates([100.0] * 10), 100.0, reglages=R3)
    assert {"atr", "structure"} <= set(REGLES)


def test_chandelier_initial_a_k_atr_sous_l_entree():
    e = ouvrir("atr", _plates([100.0, 100.5, 101.0, 101.5]), 101.5, reglages=R3)
    assert e.stop == pytest.approx(101.5 - 3.0 * 2.0)
    assert e.stop_initial == e.stop and e.cible is None


def test_structure_initiale_bornee_par_le_risque_max():
    """Sans pivot confirmé : repli à k_risque_max ATR sous l'entrée."""
    e = ouvrir("structure", _plates([100.0, 100.5, 101.0, 101.5]), 101.5, reglages=R3)
    assert e.stop == pytest.approx(101.5 - R3.k_risque_max * 2.0)


def test_structure_initiale_sous_le_dernier_creux_avec_tampon():
    bas = [10, 9, 8, 9, 10, 11, 12]           # creux confirmé en 2 (pivot 2)
    barres = _depuis_bas(bas)
    e = ouvrir("structure", barres, 13.0, reglages=R3)
    attendu = max(8.0 - R3.tampon_atr * e.atr, 13.0 - R3.k_risque_max * e.atr)
    assert e.stop == pytest.approx(attendu)
    assert e.stop < 13.0


# ------------------------------------------------------------------ cliquet

def test_chandelier_monte_avec_le_plus_haut_et_ne_recule_jamais():
    passe = _plates([100.0, 100.5, 101.0, 101.5])
    e = ouvrir("atr", passe, 101.5, reglages=R3)
    stops = [e.stop]
    for c in [102.0, 102.5, 103.0, 102.0, 101.0, 100.0]:     # hausse puis repli
        passe = passe + _plates([c])
        e = avancer(e, passe)
        stops.append(e.stop)
    assert stops == sorted(stops)                            # jamais de recul
    assert e.plus_haut == pytest.approx(103.0)
    assert stops[3] > stops[0]                               # a suivi la hausse


def test_un_choc_de_volatilite_n_abaisse_pas_le_stop():
    passe = _plates([100.0, 100.5, 101.0, 101.5])
    e = ouvrir("atr", passe, 101.5, reglages=R3)
    avant = e.stop
    e = avancer(e, passe + [Barre(101.5, 120.0, 80.0, 101.5)])    # TR énorme
    assert e.atr > 2.0 and e.stop == pytest.approx(avant)


def test_structure_ne_bouge_que_sur_creux_suivi_d_un_sommet():
    bas = [10, 9, 8, 9, 10, 11, 12, 11, 10.5, 11, 12]
    barres = _depuis_bas(bas)
    e = ouvrir("structure", barres[:4], 10.0, reglages=R3)   # entrée avant la structure
    s0 = e.stop
    for i in range(4, 9):                                    # jusqu'à i = 8
        e = avancer(e, barres[:i + 1])
    # à i = 8 : creux confirmé en 2 (8), sommet confirmé en 6 → stop sous 8 avec tampon
    assert e.stop == pytest.approx(max(s0, 8.0 - R3.tampon_atr * e.atr))
    s8 = e.stop
    for i in range(9, 11):                                   # nouveau creux (10,5) sans
        e = avancer(e, barres[:i + 1])                       # sommet derrière : immobile
    assert e.stop == pytest.approx(s8)


# ------------------------------------------------------------------ déclenchement

def test_stop_touche_execute_au_stop():
    e = ouvrir("atr", _plates([100.0, 100.5, 101.0, 101.5]), 101.5, reglages=R3)
    d = declencher(e, Barre(100.0, 100.5, e.stop - 0.1, 99.0))
    assert d == ("stop_initial", pytest.approx(e.stop), 1.0)


def test_gap_sous_le_stop_execute_a_l_ouverture():
    e = ouvrir("atr", _plates([100.0, 100.5, 101.0, 101.5]), 101.5, reglages=R3)
    d = declencher(e, Barre(e.stop - 3.0, e.stop - 2.0, e.stop - 4.0, e.stop - 3.5))
    assert d[1] == pytest.approx(e.stop - 3.0)


def test_rien_ne_se_declenche_au_dessus_du_stop():
    e = ouvrir("atr", _plates([100.0, 100.5, 101.0, 101.5]), 101.5, reglages=R3)
    assert declencher(e, Barre(101.5, 102.0, e.stop + 0.01, 101.8)) is None


def test_stop_suiveur_nomme_comme_tel():
    passe = _plates([100.0, 100.5, 101.0, 101.5])
    e = ouvrir("atr", passe, 101.5, reglages=R3)
    for c in [103.0, 105.0, 107.0]:
        passe = passe + _plates([c])
        e = avancer(e, passe)
    assert declencher(e, Barre(107.0, 107.0, e.stop - 0.1, 106.0))[0] == "stop_suiveur"


def test_prise_partielle_une_seule_fois_et_stop_prioritaire():
    reg = Reglages(periode_atr=3, pivot=2, fenetre=40, part_prise=0.25)
    e = ouvrir("atr", _plates([100.0, 100.5, 101.0, 101.5]), 101.5, reglages=reg,
               prise=True)
    risque = 101.5 - e.stop_initial
    assert e.cible == pytest.approx(101.5 + reg.r_cible_min * risque)   # aucun sommet
    motif, prix, part = declencher(e, Barre(e.cible, e.cible + 1, e.cible - 0.5, e.cible))
    assert (motif, part) == ("prise", 0.25) and prix == pytest.approx(e.cible)
    e.prise_faite = True
    assert declencher(e, Barre(e.cible, e.cible + 1, e.cible - 0.5, e.cible)) is None
    # une barre qui touche stop ET cible : le stop (hypothèse défavorable)
    e2 = ouvrir("atr", _plates([100.0, 100.5, 101.0, 101.5]), 101.5, reglages=reg,
                prise=True)
    assert declencher(e2, Barre(101.5, e2.cible + 1, e2.stop - 1, 101.0))[0] == "stop_initial"


def test_cible_sur_la_liquidite_opposee():
    """Un sommet confirmé AU-DESSUS de l'entrée, plus exigeant que le plancher en R."""
    bas = [10, 11, 12, 30, 12, 11, 10, 9, 10]                # sommet confirmé en 3
    barres = _depuis_bas(bas)
    e = ouvrir("atr", barres, 11.0, reglages=R3, prise=True)
    plancher = 11.0 + R3.r_cible_min * (11.0 - e.stop_initial)
    assert e.cible == pytest.approx(max(32.0, plancher))


# ------------------------------------------------------------------ causalité

def test_un_creux_non_confirme_ne_compte_pas():
    """Un plus-bas d'il y a UNE barre n'est pas un pivot (il en faut `pivot` après lui) :
    le stop initial se pose sous le dernier creux CONFIRMÉ, pas sous celui-là."""
    bas = [10, 9, 8, 9, 10, 11, 12, 7, 9]                    # 7 en i-1 : non confirmé
    e = ouvrir("structure", _depuis_bas(bas), 10.0, reglages=R3)
    assert e.stop == pytest.approx(max(8.0 - R3.tampon_atr * e.atr,
                                       10.0 - R3.k_risque_max * e.atr))
    assert e.stop > 7.0 - R3.tampon_atr * e.atr
