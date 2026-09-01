"""Dimensionner en NOTIONNEL ou en RISQUE — la différence est mesurable, pas doctrinale.

Mesuré sur les 477 trades réels : t de l'espérance = 0,94 en dollars contre 2,00 en R,
et le profit factor privé des cinq meilleurs trades passe de 0,89 (perdant) à 1,21. La
concentration n'était donc pas dans le signal, elle était dans la TAILLE des positions.

Ces tests vérifient les trois propriétés qui font cette différence, et surtout que le
régime historique reste identique au bit près quand l'option est éteinte.
"""

import pytest

from packages.backtest.fast_swing import _taille

BASE = dict(eq=100_000.0, fillp=50.0, atr=1.0, room=1e12, frac_cap=0.15,
            target_annual_vol=0.30, inst_vol=0.30, atr_stop=4.0, miette_min=0.5)


def test_sans_option_la_formule_historique_est_inchangee():
    """Non-régression : `risque_par_trade = 0` doit reproduire le notionnel exactement."""
    qty, stub = _taille(**BASE, risque_par_trade=0.0)
    attendu = min(BASE["eq"] * min(0.15, 0.30 / 0.30), BASE["room"]) / BASE["fillp"]
    assert qty == attendu and stub is False


def test_le_risque_ENGAGE_vaut_exactement_la_fraction_demandee():
    """Le cœur : qty × (entrée − stop) = qty × atr_stop × ATR = eq × risque."""
    qty, _ = _taille(**{**BASE, "frac_cap": 1.0}, risque_par_trade=0.01)
    assert qty * BASE["atr_stop"] * BASE["atr"] == pytest.approx(100_000.0 * 0.01)


def test_deux_titres_de_VOLATILITES_OPPOSEES_engagent_le_meme_risque():
    """La propriété que le notionnel n'a pas : un titre calme et un titre agité doivent
    risquer le MÊME montant, alors qu'ils prennent des tailles très différentes."""
    calme, _ = _taille(**{**BASE, "atr": 0.5, "frac_cap": 1.0}, risque_par_trade=0.01)
    agite, _ = _taille(**{**BASE, "atr": 5.0, "frac_cap": 1.0}, risque_par_trade=0.01)
    assert calme > agite * 5                                  # tailles très différentes
    assert calme * 4.0 * 0.5 == pytest.approx(agite * 4.0 * 5.0)   # risque identique


def test_le_notionnel_lui_engage_des_risques_TRES_inegaux():
    """Contre-épreuve : sans elle, le test précédent ne prouverait rien du défaut."""
    calme, _ = _taille(**{**BASE, "atr": 0.5}, risque_par_trade=0.0)
    agite, _ = _taille(**{**BASE, "atr": 5.0}, risque_par_trade=0.0)
    assert calme * 4.0 * 0.5 == pytest.approx(agite * 4.0 * 5.0 / 10)   # 10x d'écart


def test_les_plafonds_de_concentration_restent_des_plafonds():
    """Le risque constant ne doit JAMAIS ouvrir une ligne plus grosse que la limite."""
    qty, _ = _taille(**{**BASE, "atr": 0.01}, risque_par_trade=0.05)
    assert qty * BASE["fillp"] <= BASE["eq"] * 0.15 + 1e-9


def test_une_MIETTE_est_refusee_plutot_que_prise():
    """Le cœur du problème mesuré : quand l'exposition restante ne permet qu'un tiers de
    la taille voulue, l'ancien code prenait ce qui restait. Une miette paie les mêmes
    frais et le même slippage pour une fraction de l'avantage — et la taille de la ligne
    finit par dépendre de combien le carnet était plein, pas de la qualité du signal."""
    voulu, _ = _taille(**{**BASE, "frac_cap": 1.0}, risque_par_trade=0.01)
    _, stub = _taille(**{**BASE, "frac_cap": 1.0, "room": voulu * 50.0 * 0.30},
                      risque_par_trade=0.01)
    assert stub is True


def test_une_troncature_LEGERE_reste_acceptee():
    """Contre-épreuve : refuser toute troncature viderait le portefeuille."""
    voulu, _ = _taille(**{**BASE, "frac_cap": 1.0}, risque_par_trade=0.01)
    qty, stub = _taille(**{**BASE, "frac_cap": 1.0, "room": voulu * 50.0 * 0.80},
                        risque_par_trade=0.01)
    assert stub is False and qty < voulu


def test_un_ATR_nul_ne_divise_pas_par_zero():
    """Sans stop mesurable il n'y a pas de risque définissable — on saute."""
    qty, stub = _taille(**{**BASE, "atr": 0.0}, risque_par_trade=0.01)
    assert qty == 0.0 and stub is True
