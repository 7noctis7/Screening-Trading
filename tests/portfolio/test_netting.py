"""Netting Core/Satellite : un short tactique ne doit pas manger un DCA long en silence."""
import pytest

from packages.portfolio.netting import (attribution, conflicts, net_exposures,
                                        orders_from_targets, resolve)

SLEEVES = {"core": {"QQQ": 0.45, "AAPL": 0.10},
           "swing": {"AAPL": -0.06, "NVDA": 0.08},
           "crypto": {"BTC/USD": 0.05}}


def test_net_et_brut_ne_sont_pas_la_meme_chose():
    e = net_exposures(SLEEVES)
    assert e["instruments"]["AAPL"]["net"] == 0.04       # risque de marché porté
    assert e["instruments"]["AAPL"]["brut"] == 0.16      # financement et emprunt payés
    assert e["instruments"]["AAPL"]["oppose"] is True
    assert e["instruments"]["QQQ"]["oppose"] is False
    assert e["netting_ratio"] > 1.0                      # brut > net ⇒ du gaspillage existe


def test_le_conflit_est_chiffre_en_bps_de_nav():
    c = conflicts(SLEEVES, cost_bps=10.0)
    assert c["n_conflits"] == 1 and c["propre"] is False
    ligne = c["conflits"][0]
    assert ligne["symbole"] == "AAPL"
    assert ligne["overlap"] == 0.06                      # part qui s'annule
    assert ligne["cout_bps_du_nav"] == pytest.approx(2 * 0.06 * 10.0)
    assert conflicts({"core": {"QQQ": 0.4}, "swing": {"NVDA": 0.1}})["propre"] is True


def test_politique_net_execute_la_somme_et_previent_sur_l_attribution():
    r = resolve(SLEEVES, policy="net")
    assert r["executable"]["AAPL"] == 0.04
    assert r["economie_bps"] > 0
    assert "livres virtuels" in r["note"]
    assert r["livres_virtuels"]["swing"]["AAPL"] == -0.06   # la poche garde sa vérité


def test_core_priority_empeche_le_satellite_de_retourner_une_ligne_du_core():
    gros_short = {"core": {"AAPL": 0.10}, "swing": {"AAPL": -0.25}}
    libre = resolve(gros_short, policy="net")
    assert libre["executable"]["AAPL"] == -0.15          # le Core est retourné net SHORT

    protege = resolve(gros_short, policy="core_priority")
    assert protege["executable"]["AAPL"] == 0.0         # écrêté à plat, jamais négatif
    assert protege["ajustements"][0]["action"] == "short écrêté à plat"
    # sans conflit, core_priority ne change rien
    assert resolve(SLEEVES, policy="core_priority")["executable"]["AAPL"] == 0.04


def test_block_refuse_l_ordre_satellite_et_le_trace():
    r = resolve(SLEEVES, policy="block")
    assert r["executable"]["AAPL"] == 0.10              # position Core intacte
    assert r["ajustements"][0]["action"] == "ordre satellite refusé"
    assert r["ajustements"][0]["demande"] == 0.04
    assert r["executable"]["NVDA"] == 0.08              # les non-conflits passent


def test_politique_inconnue_refusee():
    with pytest.raises(ValueError, match="policy inconnue"):
        resolve(SLEEVES, policy="yolo")


def test_un_seul_ordre_par_instrument_et_bande_respectee():
    o = orders_from_targets({"AAPL": 0.10, "QQQ": 0.45},
                            {"AAPL": 0.04, "QQQ": 0.455, "NVDA": 0.08},
                            band=0.01, nav=100_000)
    assert o["ordres"] == {"AAPL": -0.06, "NVDA": 0.08}   # QQQ sous la bande → ignoré
    assert o["ignores"][0]["symbole"] == "QQQ"
    assert len(o["ordres"]) == len(set(o["ordres"]))      # jamais deux ordres sur un symbole
    assert o["notional"] == pytest.approx(0.14 * 100_000)


def test_attribution_separe_le_beta_du_core_de_l_alpha_du_satellite():
    a = attribution(SLEEVES, {"QQQ": 0.02, "AAPL": -0.01, "NVDA": 0.05, "BTC/USD": 0.10})
    assert a["par_poche"]["core"] == pytest.approx(0.45 * 0.02 + 0.10 * -0.01)
    assert a["par_poche"]["swing"] == pytest.approx(-0.06 * -0.01 + 0.08 * 0.05)
    assert a["total"] == pytest.approx(sum(a["par_poche"].values()))
    assert abs(sum(a["part"].values()) - 1.0) < 1e-9
