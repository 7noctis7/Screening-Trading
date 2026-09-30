"""Rejeu : la bande d'inaction se MESURE avant de se régler.

Deux questions à trancher sur données réelles, jamais sur l'intuition : (1) quelle part
des écarts à la cible la bande de production laisse-t-elle sans ordre ? (2) une bande
adaptative (coût × volatilité) fait-elle mieux ? Ces tests verrouillent les compteurs et
le branchement ; ils ne disent rien du bon réglage.
"""

from __future__ import annotations

import numpy as np
import pytest


def _jours(n):
    return [f"2020-{1 + k // 28:02d}-{1 + k % 28:02d}" for k in range(n)]


def _px(n_titres=6, n=160, graine=1):
    rng = np.random.default_rng(graine)
    jours = _jours(n)
    prix = {}
    for i in range(n_titres):
        p = 100 * np.exp(np.cumsum(rng.normal(0.0, 0.02, n)))
        prix[f"S{i}"] = dict(zip(jours, map(float, p), strict=True))
    return prix, jours


def _cibles(jours, noms, pas=5):
    rng = np.random.default_rng(7)
    out = []
    for d in jours[70::pas]:
        w = rng.dirichlet(np.ones(len(noms))) * 0.9
        out.append((d, dict(zip(noms, map(float, w), strict=True))))
    return out


def test_compteur_de_la_bande_fixe():
    """Prix immobiles, sans frais : le 1ᵉʳ passage ouvre deux lignes (deux écarts, aucun
    bloqué) ; le 2ᵉ ne trouve plus aucun écart à examiner."""
    from packages.backtest.preset_rejeu import simuler
    jours = _jours(10)
    px = {"A": {j: 100.0 for j in jours}, "B": {j: 50.0 for j in jours}}
    cible = {"A": 0.05, "B": 0.05}
    res = simuler([(jours[1], cible), (jours[4], cible)], px, jours, capital=100_000.0,
                  frais=False)
    assert res["bande"]["mode"] == "fixe"
    assert res["n_ordres"] == 2
    assert (res["bande"]["ecarts_examines"], res["bande"]["ecarts_bloques"]) == (2, 0)


def test_part_bloquee_mesuree():
    from packages.backtest.preset_rejeu import simuler
    prix, jours = _px()
    res = simuler(_cibles(jours, sorted(prix)), prix, jours, capital=100_000.0)
    b = res["bande"]
    assert b["ecarts_examines"] > 0
    assert 0.0 <= b["part_bloquee"] <= 1.0
    assert b["part_bloquee"] == pytest.approx(b["ecarts_bloques"] / b["ecarts_examines"])


def test_adaptative_repond_a_l_aversion():
    """Aversion énorme → bande au plancher (0,1 %) → plus d'ordres que la bande fixe (0,5 %) ;
    aversion infime → bande au plafond (5 %) → moins d'ordres."""
    from packages.backtest.preset_rejeu import simuler
    prix, jours = _px()
    cibles = _cibles(jours, sorted(prix))
    fixe = simuler(cibles, prix, jours, capital=100_000.0)["n_ordres"]
    serre = simuler(cibles, prix, jours, capital=100_000.0, bande="adaptative",
                    aversion=1e9)
    large = simuler(cibles, prix, jours, capital=100_000.0, bande="adaptative",
                    aversion=1e-9)
    assert serre["n_ordres"] >= fixe >= large["n_ordres"]
    assert large["bande"]["part_bloquee"] > serre["bande"]["part_bloquee"]
    assert serre["bande"]["mode"] == "adaptative" and serre["bande"]["aversion"] == 1e9


def test_mode_inconnu_refuse():
    from packages.backtest.preset_rejeu import simuler
    prix, jours = _px()
    with pytest.raises(ValueError):
        simuler(_cibles(jours, sorted(prix)), prix, jours, bande="magique")
    with pytest.raises(ValueError):
        simuler(_cibles(jours, sorted(prix)), prix, jours, bande="adaptative")  # sans aversion


def test_rejouer_de_bout_en_bout_en_bande_adaptative():
    """Le rejeu complet (décisions de PRODUCTION) accepte la bande adaptative et la rend
    visible dans son résultat ; un mode invalide est refusé avant tout calcul."""
    from packages.backtest.preset_rejeu import rejouer
    from tests.backtest.test_preset_rejeu import _panel
    data = _panel()
    res = rejouer(data, pas=20, bande="adaptative", aversion=5.0)
    assert res["available"]
    assert res["bande"]["mode"] == "adaptative" and res["bande"]["ecarts_examines"] > 0
    with pytest.raises(ValueError):
        rejouer(data, pas=20, bande="adaptative")


def test_le_plancher_ne_compte_pas_dans_la_bande():
    """Un solde imposé par le plancher de ligne ne consulte pas la bande : il n'entre
    pas au dénominateur (sinon la part bloquée paraît plus faible qu'elle n'est)."""
    from packages.backtest.preset_rejeu import simuler
    jours = _jours(10)
    px = {"A": {j: 100.0 for j in jours}, "B": {j: 50.0 for j in jours}}
    res = simuler([(jours[1], {"A": 0.05, "B": 0.05}), (jours[4], {"A": 0.05, "B": 0.005})],
                  px, jours, capital=100_000.0, frais=False)
    b = res["bande"]
    assert res["n_ordres"] == 3                            # 2 achats + le solde de B
    assert (b["ecarts_examines"], b["ecarts_bloques"]) == (2, 0)


def test_la_bande_publie_son_effet_moyen():
    """AGENTS.md, règle 4 : tout garde-fou publie son compteur ET son effet moyen."""
    from packages.backtest.preset_rejeu import simuler
    jours = _jours(10)
    px = {"A": {j: 100.0 for j in jours}}
    res = simuler([(jours[1], {"A": 0.05}), (jours[4], {"A": 0.052})], px, jours,
                  capital=100_000.0, frais=False)
    b = res["bande"]
    assert b["ecarts_bloques"] == 1                        # 200 $ < bande de 500 $
    assert b["montant_moyen_bloque"] == pytest.approx(200.0)
    assert b["ecart_poids_moyen_bloque"] == pytest.approx(0.002)
