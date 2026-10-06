"""Les quatre mesures du rapport d'espérance : définies juste avant d'être lues.

Synthétique autorisé ici pour valider les mathématiques (AGENTS.md, règle 3).
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.research import aller_retour as ar
from packages.research import capacite as cap
from packages.research import melange_meme_risque as mm
from packages.research import paris_independants as pi
from tests.backtest.test_preset_diag import Bar

T0 = datetime(2020, 1, 1, tzinfo=UTC)


def _ex(jour, sym, montant, px, cout=0.0005):
    return {"jour": jour, "sym": sym, "montant": montant, "px": px, "cout": cout}


# --- 1. Aller-retour --------------------------------------------------------

def test_fifo_vente_partielle_ferme_le_lot_le_plus_ancien():
    ex = [_ex("2020-01-02", "A", 1000, 10), _ex("2020-01-05", "A", 1100, 11),
          _ex("2020-01-09", "A", -1200, 12)]                 # 100 titres vendus
    ars, ouverts = ar.apparier(ex)
    (r,) = ars
    assert r["px_achat"] == 10 and r["q"] == pytest.approx(100) and ouverts == 1
    assert ar.rendement_net(r) == pytest.approx(12 / 10 - 1 - 0.001)


def test_vente_sur_deux_lots_donne_deux_allers_retours():
    ex = [_ex("d1", "A", 500, 10), _ex("d2", "A", 500, 20),
          _ex("d3", "A", -2250, 30)]                         # 75 titres vendus
    ars, ouverts = ar.apparier(ex)
    assert [a["px_achat"] for a in ars] == [10, 20] and ouverts == 0
    assert sum(a["q"] for a in ars) == pytest.approx(75)


def test_esperance_ponderee_et_plancher():
    assert ar.esperance([0.01] * 10, [1] * 10)["status"] == "UNCALIBRATED"
    nets = [0.10] * 20 + [-0.02] * 20
    e = ar.esperance(nets, [1.0] * 20 + [9.0] * 20)
    assert e["esperance_ponderee"] == pytest.approx((0.10 * 20 - 0.02 * 180) / 200)
    assert e["esperance_simple"] == pytest.approx(0.04) and e["taux_gain"] == 0.5
    assert e["ic95"][0] <= e["esperance_ponderee"] <= e["ic95"][1]


# --- 2. Même risque ---------------------------------------------------------

def test_alpha_meme_drawdown_retrouve_la_dilution():
    rq = np.random.default_rng(0).normal(0.0005, 0.015, 1500)
    livre = 0.4 * rq                                       # QQQ dilué à 40 %
    a = mm.alpha_meme_drawdown(livre, rq)
    assert a == pytest.approx(0.4, abs=0.01)
    r = mm.comparer(livre, rq, n_essais=100)
    assert abs(r["ecart_annualise"]) < 1e-3 and r["ic95"][0] <= 0 <= r["ic95"][1]


def test_un_livre_moins_investi_ne_bat_pas_le_melange():
    rq = np.random.default_rng(1).normal(0.0006, 0.015, 1500)
    livre = 0.5 * rq - 0.0001                               # dilué ET un coût
    r = mm.comparer(livre, rq, n_essais=50)
    assert r["ecart_annualise"] < 0 and r["plafonne"] is False


def test_alpha_plafonne_a_un_sans_levier():
    rq = np.random.default_rng(2).normal(0.0, 0.01, 800)
    assert mm.alpha_meme_drawdown(3 * rq, rq) == 1.0


# --- 3. Paris indépendants --------------------------------------------------

def test_n_effectif_bornes():
    rng = np.random.default_rng(3)
    commun = rng.normal(0, 1, 200)
    identiques = np.vstack([commun] * 10)
    independants = rng.normal(0, 1, (10, 2000))
    assert pi.n_effectif(identiques + 1e-9 * rng.normal(0, 1, (10, 200))) < 1.1
    assert pi.n_effectif(independants) > 9.0


def test_par_decision_point_in_time():
    rng = np.random.default_rng(4)
    jours = [(T0 + timedelta(days=i)).date().isoformat() for i in range(300)]
    prix = {s: dict(zip(jours, 100 * np.cumprod(1 + rng.normal(0, 0.01, 300)),
                        strict=True)) for s in "ABCD"}
    lignes = pi.par_decision([(jours[200], {"A": .25, "B": .25, "C": .25, "D": .25})],
                             prix)
    futur = {s: {**p, **{j: 1e6 for j in jours[201:]}} for s, p in prix.items()}
    lignes2 = pi.par_decision([(jours[200], {"A": .25, "B": .25, "C": .25, "D": .25})],
                              futur)
    assert lignes[0]["n_eff"] == pytest.approx(lignes2[0]["n_eff"])
    assert pi.resume(lignes, 10)["paris_independants_par_an"] == pytest.approx(
        lignes[0]["n_eff"] * 25.2)


# --- 4. Capacité ------------------------------------------------------------

def _data_marche(n=80, vol=1e5):
    return {"A": [Bar(T0 + timedelta(days=i), 10, 10, 10,
                      10 * (1 + 0.01 * (i % 2)), vol) for i in range(n)]}


def test_marche_ne_lit_pas_le_jour_meme():
    data = _data_marche()
    m = cap.Marche(data)
    j = (T0 + timedelta(days=40)).date().isoformat()
    adv, _ = m.adv_sigma("A", j)
    data["A"][40] = Bar(data["A"][40].ts, 10, 10, 10, 10, 1e12)   # volume du jour
    assert cap.Marche(data).adv_sigma("A", j)[0] == adv


def test_capacite_finie_et_decroissante_avec_y():
    data = _data_marche()
    jours = [(T0 + timedelta(days=i)).date().isoformat() for i in range(30, 70)]
    ars = [{"sym": "A", "achat": jours[i], "vente": jours[i + 1], "q": 100.0,
            "px_achat": 10.0, "px_vente": 10.1, "cout_achat": 0.0005,
            "cout_vente": 0.0005, "notionnel": 1000.0} for i in range(0, 38)]
    res = cap.capacite(ars, data, capital=100_000)
    k5, k10 = res["par_y"]["Y=0.5"]["k"], res["par_y"]["Y=1.0"]["k"]
    assert res["available"] and 0 < k10 < k5
    p = [cap._param(cap.Marche(data), a) for a in ars]
    assert cap.esperance_a_l_echelle(ars, p, k5, 0.5) == pytest.approx(0, abs=1e-6)


def test_esperance_negative_sans_impact_capacite_nulle():
    data = _data_marche()
    jours = [(T0 + timedelta(days=i)).date().isoformat() for i in range(30, 70)]
    ars = [{"sym": "A", "achat": jours[i], "vente": jours[i + 1], "q": 1.0,
            "px_achat": 10.0, "px_vente": 9.99, "cout_achat": 0.0005,
            "cout_vente": 0.0005, "notionnel": 10.0} for i in range(0, 38)]
    assert cap.capacite(ars, data, 1e5)["par_y"]["Y=0.5"]["k"] == 0.0


def test_un_volume_nan_n_est_pas_un_volume():
    """06/10, VPS : un NaN dans la fenêtre passait `mean() <= 0`, l'ADV valait NaN
    et `min(1, q / nan)` = 1 : participation 100 %, impact = Y·σ à toute taille."""
    data = _data_marche()
    j = (T0 + timedelta(days=40)).date().isoformat()
    adv, _ = cap.Marche(data).adv_sigma("A", j)
    b = data["A"][30]
    data["A"][30] = Bar(b.ts, b.open, b.high, b.low, b.close, float("nan"))
    adv_nan, _ = cap.Marche(data).adv_sigma("A", j)
    assert np.isfinite(adv_nan) and adv_nan == pytest.approx(adv)
    for i in range(20, 40):                                   # fenêtre presque vide
        b = data["A"][i]
        data["A"][i] = Bar(b.ts, b.open, b.high, b.low, b.close, float("nan"))
    assert cap.Marche(data).adv_sigma("A", j) is None


def test_l_impact_croit_au_dela_d_un_adv():
    """Plafonner la participation à 100 % rendait la capacité infinie."""
    assert cap.impact(4e5, 1e5, 0.02, 1.0) == pytest.approx(2 * cap.impact(1e5, 1e5,
                                                                         0.02, 1.0))
    assert cap.impact(1e5, 1e5, 0.02, 0.5) == pytest.approx(0.01)


def test_participation_publiee():
    data = _data_marche(vol=1e3)
    jours = [(T0 + timedelta(days=i)).date().isoformat() for i in range(30, 70)]
    ars = [{"sym": "A", "achat": jours[i], "vente": jours[i + 1], "q": 100.0,
            "px_achat": 10.0, "px_vente": 10.1, "cout_achat": 0.0005,
            "cout_vente": 0.0005, "notionnel": 1000.0} for i in range(0, 38)]
    pa = cap.capacite(ars, data, 1e5)["participation"]
    assert pa["n"] == 76 and pa["mediane"] == pytest.approx(0.1)
    assert pa["part_sup_1pct"] == 1.0 and pa["part_sup_100pct"] == 0.0
