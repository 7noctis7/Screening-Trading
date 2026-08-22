"""La poussière du compte réel : comment elle naît, et pourquoi elle ne partait plus.

Reproduit le cas observé (une trentaine de lignes à 0,01–3 $ sur Alpaca) et fige les deux
règles qui l'empêchent : une sortie complète ignore la bande, une ouverture sous plancher
n'a pas lieu.
"""
from packages.execution.rebalance_plan import (
    MIN_LIGNE_DEFAUT, RATIO_SORTIE, Intention, decider, min_ligne, plan, poussiere,
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


def test_une_ligne_deja_tenue_sous_le_plancher_est_soldee_pas_reduite():
    """LE changement de fond : le plancher ne gardait que l'ouverture, donc une ligne trop
    petite survivait indéfiniment, protégée par la bande. Elle est désormais soldée."""
    i = decider(cible=20.0, detenu=800.0, bande=1.0)
    assert i.action == "solder" and i.liquidation
    assert i.montant == 800.0


def test_hysteresis_pas_de_va_et_vient_autour_du_plancher():
    """Une cible qui oscille autour du plancher ne doit pas faire acheter puis solder en boucle."""
    p = MIN_LIGNE_DEFAUT
    assert decider(cible=p * 0.9, detenu=p, bande=1.0).action == "rien"      # zone morte
    assert decider(cible=p * 0.5, detenu=p, bande=1.0).action == "solder"    # franchement dessous
    assert decider(cible=p * 1.1, detenu=p, bande=1.0).action == "acheter"   # franchement dessus


def test_le_plancher_est_reglable(monkeypatch):
    monkeypatch.setenv("QUANT_MIN_POSITION", "1000")
    assert min_ligne() == 1000.0
    assert decider(cible=700.0, detenu=0.0, bande=1.0).action == "rien"


def test_un_plancher_illisible_retombe_sur_le_defaut(monkeypatch):
    """Une faute de frappe ne doit pas désactiver silencieusement le garde-fou."""
    monkeypatch.setenv("QUANT_MIN_POSITION", "cinq-cents")
    assert min_ligne() == MIN_LIGNE_DEFAUT
    monkeypatch.setenv("QUANT_MIN_POSITION", "-40")
    assert min_ligne() == MIN_LIGNE_DEFAUT


def test_la_bande_garde_son_role_au_dessus_du_plancher():
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
    """Les lignes réellement observées sur le compte, passées au plan.

    Y compris les positions de quelques centaines de dollars : sous le plancher, elles ne
    pèsent rien et doivent partir aussi — pas seulement la poussière à 0,01 $.
    """
    detenus = {"QQQ": 50_056.0, "SOLUSD": 3_634.0, "PHM": 780.0, "SPG": 983.0, "SJM": 1_223.0,
               "TEN": 3.01, "TSM": 2.26, "OSCR": 2.30, "ASML": 1.67, "PBI": 1.06, "STT": 0.63,
               "HOOD": 0.56, "M": 0.50, "KSS": 0.01, "HST": 0.01, "VNO": 0.01}
    cibles = {"QQQ": 50_000.0, "SOLUSD": 3_600.0}
    p = plan(cibles, detenus, BANDE)
    gardees = sorted(k for k, v in p.items() if v.action == "rien")
    assert gardees == ["QQQ", "SOLUSD"]
    # Tout le reste part, quelle que soit la taille : 0,01 $ comme 1 223 $.
    soldees = {k for k, v in p.items() if v.action == "solder"}
    assert soldees == set(detenus) - {"QQQ", "SOLUSD"}
    assert all(p[k].liquidation for k in soldees)


def test_le_diagnostic_de_poussiere_nomme_les_lignes():
    d = {"QQQ": 50_056.0, "TEN": 3.01, "ASML": 1.67, "PETIT": 400.0, "ZERO": 0.0}
    assert poussiere(d) == {"TEN": 3.01, "ASML": 1.67, "PETIT": 400.0}
    assert poussiere(d, seuil=5.0) == {"TEN": 3.01, "ASML": 1.67}


def test_montants_negatifs_ne_cassent_rien():
    """Une valeur de marché négative (short mal lu) ne doit pas produire un ordre absurde."""
    assert decider(-5.0, -5.0, BANDE).action == "rien"
    i = decider(0.0, -3.0, BANDE)
    assert i.action == "rien"


def test_intention_expose_agit():
    assert Intention("rien", 0.0, "x").agit is False
    assert decider(0.0, 100.0, BANDE).agit is True


def test_plancher_par_defaut_documente():
    """500 $ sur ~77 000 $ = « une ligne pèse au moins 0,65 %, sinon elle n'a pas sa place »."""
    assert MIN_LIGNE_DEFAUT == 500.0
    assert RATIO_SORTIE == 0.8
