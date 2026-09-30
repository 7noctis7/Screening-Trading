"""Rejeu : les sorties (stop, prise partielle) branchées sur les décisions de production.

Ce qui doit tenir pour que la comparaison « avec / sans sorties » soit honnête :
  * le stop s'exécute à SON prix (ou à l'ouverture sur gap), pas au close du jour ;
  * une ligne sortie n'est pas rachetée par le rééquilibrage suivant pendant le délai de
    carence — sinon on mesure un aller-retour, pas une sortie ;
  * le cœur indiciel n'est jamais géré ; sans déclenchement, le rejeu est IDENTIQUE ;
  * modifier les séances postérieures à `d` ne change rien jusqu'à `d`.
"""

from __future__ import annotations

import pytest

from packages.strategies.sorties_suiveuses import Barre, Reglages

R3 = Reglages(periode_atr=3, pivot=2, fenetre=40)


def _jours(n):
    return [f"2020-{1 + k // 28:02d}-{1 + k % 28:02d}" for k in range(n)]


def _marche(n=30, choc=None):
    """A : cours plat à 100 (TR = 2 → ATR 2, stop Chandelier à 94). `choc` = {i: barre}."""
    jours = _jours(n)
    barres = {j: Barre(100.0, 101.0, 99.0, 100.0) for j in jours}
    for i, b in (choc or {}).items():
        barres[jours[i]] = b
    ohlc = {"A": barres}
    prix = {"A": {j: b.close for j, b in barres.items()}}
    return jours, prix, ohlc


def _surv(ohlc, jours, **kw):
    from packages.backtest.rejeu_sorties import Surveillance
    return Surveillance(kw.pop("regle", "atr"), ohlc, jours, reglages=R3, **kw)


def _sim(jours, prix, cibles, sorties=None):
    from packages.backtest.preset_rejeu import simuler
    return simuler(cibles, prix, jours, capital=100_000.0, frais=False, sorties=sorties)


def test_le_stop_s_execute_a_son_prix_pas_au_close():
    jours, prix, ohlc = _marche(choc={10: Barre(99.0, 99.5, 90.0, 91.0)})
    surv = _surv(ohlc, jours)
    res = _sim(jours, prix, [(jours[5], {"A": 0.10})], surv)
    assert res["equity"][-1] == pytest.approx(90_000 + 10_000 * 94 / 100)
    sans = _sim(jours, prix, [(jours[5], {"A": 0.10})])
    k = sans["dates"].index(jours[10])                 # le jour du choc, marqué au close
    assert sans["equity"][k] == pytest.approx(90_000 + 10_000 * 91 / 100)
    assert res["equity"][k] == pytest.approx(90_000 + 10_000 * 94 / 100)
    assert surv.resume()["sorties"] == {"stop_initial": 1}


def test_gap_sous_le_stop_sort_a_l_ouverture():
    jours, prix, ohlc = _marche(choc={10: Barre(88.0, 89.0, 87.0, 88.5)})
    res = _sim(jours, prix, [(jours[5], {"A": 0.10})], _surv(ohlc, jours))
    assert res["equity"][-1] == pytest.approx(90_000 + 10_000 * 88 / 100)


def test_pas_de_rachat_pendant_la_carence():
    jours, prix, ohlc = _marche(choc={10: Barre(99.0, 99.5, 90.0, 91.0)})
    # après le choc, le cours revient à 100 : une décision à J12 voudrait racheter
    for j in jours[11:]:
        ohlc["A"][j] = Barre(100.0, 101.0, 99.0, 100.0)
        prix["A"][j] = 100.0
    cibles = [(jours[5], {"A": 0.10}), (jours[12], {"A": 0.10}), (jours[25], {"A": 0.10})]
    surv = _surv(ohlc, jours, cooldown=10)
    res = _sim(jours, prix, cibles, surv)
    # J13 : rachat refusé (carence jusqu'à J20) ; J26 : rachat autorisé
    assert res["n_ordres"] == 3                       # achat, stop, rachat de J26
    assert surv.resume()["rachats_refuses"] >= 1


def test_le_coeur_n_est_jamais_gere():
    jours, prix, ohlc = _marche(choc={10: Barre(99.0, 99.5, 90.0, 91.0)})
    surv = _surv(ohlc, jours, exclus={"A"})
    res = _sim(jours, prix, [(jours[5], {"A": 0.10})], surv)
    k = res["dates"].index(jours[10])
    assert res["equity"][k] == pytest.approx(90_000 + 10_000 * 91 / 100)   # pas de stop
    assert surv.resume()["sorties"] == {}


def test_sans_declenchement_le_rejeu_est_identique():
    jours, prix, ohlc = _marche()
    cibles = [(jours[5], {"A": 0.10}), (jours[15], {"A": 0.05})]
    avec = _sim(jours, prix, cibles, _surv(ohlc, jours, regle="structure"))
    sans = _sim(jours, prix, cibles)
    assert avec["equity"] == pytest.approx(sans["equity"])
    assert avec["n_ordres"] == sans["n_ordres"]


def test_prise_partielle_puis_cible_reduite_pendant_la_carence():
    # cible = 100 + 2R, R = 6 → 112 ; J10 touche 113 ; puis retour à 100
    jours, prix, ohlc = _marche(choc={10: Barre(100.0, 113.0, 99.0, 100.0)})
    surv = _surv(ohlc, jours, prise=True, cooldown=10)
    cibles = [(jours[5], {"A": 0.10}), (jours[12], {"A": 0.10})]
    res = _sim(jours, prix, cibles, surv)
    assert surv.resume()["sorties"] == {"prise": 1}
    part = R3.part_prise
    # vendu 1/3 à 112 ; la décision de J12 vise 10 % × (1 − 1/3) : pas de rachat au-delà
    ligne = res["poids_final"]["A"]
    assert ligne == pytest.approx(0.10 * (1 - part), abs=0.006)


def test_l_avenir_ne_change_pas_le_passe():
    jours, prix, ohlc = _marche(choc={10: Barre(99.0, 99.5, 90.0, 91.0)})
    r1 = _sim(jours, prix, [(jours[5], {"A": 0.10})], _surv(ohlc, jours))
    for j in jours[15:]:
        ohlc["A"][j] = Barre(50.0, 51.0, 49.0, 50.0)
        prix["A"][j] = 50.0
    r2 = _sim(jours, prix, [(jours[5], {"A": 0.10})], _surv(ohlc, jours))
    k = r1["dates"].index(jours[14])
    assert r1["equity"][:k + 1] == pytest.approx(r2["equity"][:k + 1])


def test_comparaison_de_bout_en_bout_sur_les_decisions_de_production():
    """Mêmes décisions pour les deux jambes : la jambe « sans » est le rejeu lui-même."""
    from packages.backtest.preset_rejeu import rejouer
    from packages.backtest.rejeu_sorties import comparer_sorties
    from tests.backtest.test_preset_rejeu import _panel
    data = _panel()
    res = comparer_sorties(data, regle="atr", pas=20)
    assert res["available"]
    base = rejouer(data, pas=20)
    assert res["sans"]["equity"] == pytest.approx(base["equity"])
    assert set(res) >= {"sans", "avec", "delta", "sorties", "statut"}
    assert res["statut"] == "SHADOW_UNCALIBRATED"
