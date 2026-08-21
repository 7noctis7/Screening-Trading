"""Pipeline 4 couches : l'entonnoir doit dire la vérité sur le souffle qu'il laisse passer."""

from datetime import datetime, timezone

import numpy as np
import pytest

from packages.fundamentals.models import Financials
from packages.screening.alpha_pipeline import (Seuils, _viole, metriques_qualite,
                                               run_pipeline, signal_momentum, stop_atr,
                                               taille_position, valorisation_dcf)

T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _fin(sym, price=100.0, revenue=1000.0, net=200.0, fcf=180.0, equity=800.0,
         debt=300.0, growth=0.20, shares=100.0):
    return Financials(symbol=sym, as_of=T0, sector="Tech", price=price, shares=shares,
                      revenue=revenue, gross_profit=revenue * 0.6, ebit=net * 1.3,
                      ebitda=net * 1.5, net_income=net, total_equity=equity,
                      total_debt=debt, cash=100.0, fcf=fcf, revenue_growth=growth)


def _prix(seed=0, n=400, drift=0.002, vol=0.015, hausse=True):
    """Chemin nettement tendanciel : on teste la LOGIQUE du filtre, pas la chance du tirage."""
    rng = np.random.default_rng(seed)
    r = rng.normal(drift if hausse else -drift, vol, n)
    c = 100 * np.exp(np.cumsum(r))
    return {"closes": c, "highs": c * 1.01, "lows": c * 0.99,
            "volumes": np.r_[np.full(n - 1, 1e6), 3e6], "returns": r}


# ---------------- couche 1 ----------------------------------------------------
def test_un_critere_non_mesure_n_est_JAMAIS_compte_comme_satisfait():
    m = metriques_qualite(_fin("A"))
    assert m["quick_ratio"] is None                      # non calculable depuis Financials
    assert m["net_margin"] == pytest.approx(0.2)
    assert m["debt_to_equity"] == pytest.approx(0.375)
    sans_croissance = metriques_qualite(
        Financials("B", T0, "Tech", 100.0, 100.0, 1000.0, 600.0, 260.0, 300.0, 200.0,
                   800.0, 300.0, 100.0, 180.0))
    assert sans_croissance["revenue_growth"] is None
    assert not any("croissance" in v for v in _viole(sans_croissance, Seuils()))


def test_les_couperets_signalent_ce_qui_est_reellement_viole():
    s = Seuils()
    v = _viole(metriques_qualite(_fin("C", net=50.0, growth=0.02, debt=900.0)), s)
    assert any("marge" in x for x in v) and any("croissance" in x for x in v)
    assert any("D/E" in x for x in v)
    perte = metriques_qualite(_fin("D", net=-10.0))
    assert perte["price_to_earnings"] is None
    assert any("PER non calculable" in x for x in _viole(perte, s))


# ---------------- couche 2 ----------------------------------------------------
def test_le_dcf_publie_une_bande_et_avoue_quand_il_ne_conclut_pas():
    v = valorisation_dcf(_fin("E", price=100.0, fcf=180.0))
    assert v["available"] and v["bande_basse"] <= v["marge_securite"] <= v["bande_haute"]
    # un prix calé au milieu de la bande => le signe s'inverse => fragile
    milieu = _fin("F", price=100.0)
    juste = valorisation_dcf(milieu)["juste_valeur"]
    frag = valorisation_dcf(_fin("F", price=juste))
    assert frag["fragile"] is True and "ne conclut pas" in frag["note"]
    assert valorisation_dcf(_fin("G", fcf=-10.0))["available"] is False


# ---------------- couche 3 ----------------------------------------------------
def test_les_trois_conditions_de_momentum():
    ok = signal_momentum(**{k: _prix(1)[k] for k in ("closes", "volumes")})
    assert ok["valide"] and ok["au_dessus_ema50"] and ok["tendance_haussiere"]
    baisse = _prix(2, hausse=False)
    assert signal_momentum(baisse["closes"], baisse["volumes"])["valide"] is False
    faible = _prix(1)
    faible["volumes"] = np.r_[np.full(399, 3e6), 1e6]      # volume du jour sous la moyenne
    assert signal_momentum(faible["closes"], faible["volumes"])["volume_confirme"] is False
    assert signal_momentum(np.arange(50, dtype=float))["available"] is False


# ---------------- couche 4 ----------------------------------------------------
def test_le_budget_d_ES_egalise_le_risque_entre_actifs_de_vol_differente():
    calme = taille_position(_prix(3, vol=0.008)["returns"], es_budget=0.01, cap=1.0)
    agite = taille_position(_prix(3, vol=0.05)["returns"], es_budget=0.01, cap=1.0)
    assert calme["poids"] > agite["poids"] * 2            # moins de vol → plus de poids
    assert calme["es_95"] < agite["es_95"]
    # contribution au risque de queue ≈ identique : c'est tout l'objet du budget d'ES
    assert calme["poids"] * calme["es_95"] == pytest.approx(agite["poids"] * agite["es_95"],
                                                            rel=1e-3)   # valeurs arrondies


def test_le_plafond_de_5_pourcent_est_dur_et_kelly_reste_uncalibrated_sans_trades():
    t = taille_position(_prix(4, vol=0.003)["returns"], es_budget=0.05, cap=0.05)
    assert t["poids"] == 0.05 and t["fraction_kelly"] is None
    assert t["statut"].startswith("UNCALIBRATED")
    avec = taille_position(_prix(4)["returns"], roundtrips=list(_prix(5)["returns"][:200]),
                           cap=1.0)
    assert avec["fraction_kelly"] is not None and avec["statut"] == "calibré"


def test_stop_atr_s_adapte_a_la_volatilite():
    calme, agite = _prix(6, vol=0.005), _prix(6, vol=0.04)
    a = stop_atr(calme["highs"], calme["lows"], calme["closes"])
    b = stop_atr(agite["highs"], agite["lows"], agite["closes"])
    assert a["available"] and a["stop_long"] < calme["closes"][-1]
    assert b["distance_pct"] > a["distance_pct"]
    assert stop_atr([1, 2], [1, 2], [1, 2])["available"] is False


# ---------------- l'entonnoir : LE test qui compte ---------------------------
def _univers(n=40):
    """Univers réaliste : les sociétés de QUALITÉ se paient cher (PER élevé)."""
    rng = np.random.default_rng(0)
    fins, prix = [], {}
    for i in range(n):
        qualite = i < n // 3
        marge = 0.25 if qualite else 0.08
        croiss = 0.22 if qualite else 0.04
        net = 1000.0 * marge
        # le marché price la qualité : PER ~40 pour les bonnes, ~14 pour les autres
        per = 40.0 if qualite else 14.0
        fins.append(_fin(f"S{i}", price=per * net / 100.0, revenue=1000.0, net=net,
                         fcf=net * 0.9, growth=croiss,
                         debt=200.0 if qualite else 700.0))
        prix[f"S{i}"] = _prix(seed=100 + i, hausse=bool(rng.random() > 0.3))
    return fins, prix


def test_la_conjonction_de_couperets_asseche_le_souffle():
    """Marge > 20 % ET croissance > 15 % ET PER < 25 est presque contradictoire : le marché
    price précisément la qualité-croissance au-dessus de 25× les bénéfices."""
    fins, prix = _univers()
    strict = run_pipeline(fins, prix, mode="strict")
    rank = run_pipeline(fins, prix, mode="rank")
    assert len(strict["candidats"]) < len(rank["candidats"])
    assert strict["souffle_suffisant"] is False            # trop peu de lignes pour un IR
    # l'entonnoir doit expliquer OÙ ça se ferme : ici dès la COUCHE 1
    couches = {e["couche"]: e for e in strict["entonnoir"]}
    assert couches["1 · qualité"]["sortent"] == 0          # la conjonction vide l'univers
    assert couches["1 · qualité"]["entrent"] == 40
    assert all(e["entrent"] >= e["sortent"] for e in strict["entonnoir"])
    assert "point-in-time" in rank["avertissement"]


def test_le_mode_rank_preserve_le_souffle_et_publie_les_raisons():
    fins, prix = _univers(60)
    r = run_pipeline(fins, prix, mode="rank")
    assert r["mode"] == "rank"
    assert len(r["candidats"]) >= 1
    assert 0.0 <= r["gross_expose"] <= len(r["candidats"]) * 0.05 + 1e-9
    assert all(c.taille["poids"] <= 0.05 for c in r["candidats"])
    assert any(v for v in r["rejetes"].values())          # chaque rejet est motivé
    with pytest.raises(ValueError):
        run_pipeline(fins, prix, mode="yolo")
