"""Écart de réplication modèle ↔ réel, et plan de convergence.

Cas de référence : le compte réel du 24/08 — QQQ commun, satellite modèle de 13 actions absent,
poche crypto de ~30 % que le modèle ne détient pas.
"""

from packages.portfolio.replication import (active_share, cle, ecarts, plan_convergence, poids)

MODELE = [{"symbol": "QQQ", "value": 7790}, {"symbol": "SLV", "value": 290},
          {"symbol": "AA", "value": 250}, {"symbol": "GLW", "value": 240},
          {"symbol": "MU", "value": 190}, {"symbol": "AMCR", "value": 30}]
REEL = [{"symbol": "QQQ", "market_value": 69700}, {"symbol": "SOLUSD", "market_value": 5300},
        {"symbol": "BTCUSD", "market_value": 4300}, {"symbol": "ETHUSD", "market_value": 3300}]


def test_cle_apparie_les_variantes_crypto():
    assert cle("BTC/USD") == cle("BTC-USD") == cle("BTCUSDT") == cle("BTCUSD") == "BTC"
    assert cle("QQQ") == "QQQ"
    assert cle("USD") == "USD"           # pas de suffixe à retirer sur un symbole qui EST le suffixe


def test_poids_normalise_et_ignore_les_montants():
    w = poids(REEL, "market_value")
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert w["QQQ"] > w["SOL"] > w["ETH"]


def test_active_share_vaut_zero_pour_une_replication_parfaite():
    w = {"A": 0.6, "B": 0.4}
    assert active_share(w, w) == 0.0
    assert active_share({"A": 1.0}, {"B": 1.0}) == 1.0


def test_active_share_egale_la_poche_hors_modele():
    """LE point du 24/08 : tant que la poche crypto existe, l'écart ne peut pas descendre
    en dessous de son poids — acheter le satellite ne suffit pas."""
    p = plan_convergence(MODELE, REEL, 100_000.0, plancher=1000.0)
    assert abs(p["active_share_apres"] - p["poche_hors_modele"]) < 1e-3
    assert p["active_share_apres"] <= p["active_share_avant"] + 1e-9


def test_liquider_la_poche_fait_tomber_l_ecart():
    p = plan_convergence(MODELE, REEL, 100_000.0, plancher=1000.0, liquider_hors_modele=True)
    assert p["active_share_apres"] < 0.10
    soldes = [o for o in p["ordres"] if o["action"] == "solder"]
    assert {o["symbole"] for o in soldes} == {"SOLUSD", "BTCUSD", "ETHUSD"}
    assert all(o["liquidation"] for o in soldes)      # sortie en QUANTITÉ, jamais en montant


def test_plancher_ecarte_les_lignes_trop_petites():
    """AMCR pèse 0,3 % du modèle → 300 $ sur 100 000 $ : sous le plancher, on ne l'ouvre pas."""
    p = plan_convergence(MODELE, REEL, 100_000.0, plancher=1000.0)
    assert "AMCR" in p["non_replicables"]
    assert all(o["symbole"] != "AMCR" for o in p["ordres"])


def test_petit_compte_rend_le_modele_non_replicable():
    """Sur un compte de 5 000 $, presque aucune ligne du satellite n'atteint le plancher."""
    p = plan_convergence(MODELE, REEL, 5_000.0, plancher=1000.0)
    assert len(p["non_replicables"]) >= 4 and p["plancher_bloquant"]


def test_poche_conservee_ne_genere_aucun_ordre_de_vente():
    p = plan_convergence(MODELE, REEL, 100_000.0, plancher=1000.0)
    assert not [o for o in p["ordres"] if o["symbole"].endswith("USD") and o["action"] != "rien"]


def test_ecarts_trie_par_amplitude_et_qualifie_chaque_ligne():
    lignes = ecarts(MODELE, REEL)
    statuts = {l.symbole: l.statut for l in lignes}
    assert statuts["QQQ"] == "commune"
    assert statuts["SOLUSD"] == "hors_modele"
    assert statuts["AMCR"] == "modele_seul"
    amplitudes = [abs(l.ecart) for l in lignes]
    assert amplitudes == sorted(amplitudes, reverse=True)


def test_equity_nulle_ne_leve_pas():
    p = plan_convergence(MODELE, REEL, 0.0)
    assert p["available"] is False and p["ordres"] == []
