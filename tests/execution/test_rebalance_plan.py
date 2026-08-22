"""La poussière du compte réel : comment elle naît, et pourquoi elle ne partait plus.

Reproduit le cas observé (une trentaine de lignes à 0,01–3 $ sur Alpaca) et fige les deux
règles qui l'empêchent : une sortie complète ignore la bande, une ouverture sous plancher
n'a pas lieu.
"""
from packages.execution.rebalance_plan import (
    MIN_OUVERTURE, Intention, decider, plan, poussiere,
)

BANDE = 385.0        # 0,5 % d'un capital de ~77 000 $, comme en production


def test_le_residu_etait_immortel_il_est_maintenant_solde():
    """Le défaut d'origine : 0,50 $ détenu, cible 0 → |delta| < bande → jamais vendu."""
    i = decider(cible=0.0, detenu=0.50, bande=BANDE)
    assert i.action == "solder" and i.liquidation
    assert i.montant == 0.50


def test_solder_ignore_la_bande_quel_que_soit_le_montant():
    for montant in (0.02, 1.67, 120.0, 9_000.0):
        i = decider(0.0, montant, BANDE)
        assert i.action == "solder", montant
        assert i.liquidation


def test_on_nouvre_pas_une_ligne_qui_sera_la_poussiere_de_demain():
    i = decider(cible=12.0, detenu=0.0, bande=1.0)
    assert i.action == "rien" and "plancher" in i.motif


def test_le_plancher_ne_bloque_pas_un_renforcement_dune_ligne_existante():
    """Le plancher vise l'OUVERTURE. Une ligne déjà tenue peut être ajustée finement."""
    i = decider(cible=20.0, detenu=800.0, bande=1.0)
    assert i.action == "alleger" and abs(i.montant - 780.0) < 1e-9


def test_la_bande_garde_son_role_entre_les_deux():
    assert decider(10_000.0, 10_200.0, BANDE).action == "rien"
    assert decider(10_000.0, 10_500.0, BANDE).action == "alleger"
    assert decider(10_500.0, 10_000.0, BANDE).action == "acheter"


def test_rien_a_solder_quand_rien_nest_detenu():
    assert decider(0.0, 0.0, BANDE).action == "rien"
    # Un centime déclaré par le courtier EST une position : on la solde.
    assert decider(0.0, 0.01, BANDE).action == "solder"


def test_une_ligne_detenue_hors_cibles_est_toujours_soldee():
    """Garantit qu'aucune position ne peut se cacher du rééquilibrage."""
    p = plan(cibles={"QQQ": 50_000.0}, detenus={"QQQ": 50_100.0, "VIEUX": 3.01}, bande=BANDE)
    assert p["QQQ"].action == "rien"
    assert p["VIEUX"].action == "solder" and p["VIEUX"].liquidation


def test_le_cas_reel_complet():
    """Les lignes réellement observées sur le compte, passées au plan."""
    detenus = {"QQQ": 50_056.0, "SOLUSD": 3_634.0, "TEN": 3.01, "TSM": 2.26, "OSCR": 2.30,
               "ASML": 1.67, "PBI": 1.06, "STT": 0.63, "SAN": 0.61, "HOOD": 0.56, "M": 0.50,
               "KSS": 0.01, "HST": 0.01, "VNO": 0.01, "PSA": 0.01}
    cibles = {"QQQ": 50_000.0, "SOLUSD": 3_600.0}
    p = plan(cibles, detenus, BANDE)
    soldees = sorted(k for k, v in p.items() if v.action == "solder")
    assert soldees == ["ASML", "HOOD", "HST", "KSS", "M", "OSCR", "PBI", "PSA",
                       "SAN", "STT", "TEN", "TSM", "VNO"]
    assert all(p[k].liquidation for k in soldees)
    assert p["QQQ"].action == "rien" and p["SOLUSD"].action == "rien"


def test_le_diagnostic_de_poussiere_nomme_les_lignes():
    d = {"QQQ": 50_056.0, "TEN": 3.01, "ASML": 1.67, "GROS": 900.0, "ZERO": 0.0}
    assert poussiere(d) == {"TEN": 3.01, "ASML": 1.67}


def test_montants_negatifs_ne_cassent_rien():
    """Une valeur de marché négative (short mal lu) ne doit pas produire un ordre absurde."""
    assert decider(-5.0, -5.0, BANDE).action == "rien"
    i = decider(0.0, -3.0, BANDE)
    assert i.action == "rien"


def test_intention_expose_agit():
    assert Intention("rien", 0.0, "x").agit is False
    assert decider(0.0, 100.0, BANDE).agit is True


def test_plancher_par_defaut_documente():
    assert MIN_OUVERTURE == 25.0
