"""IC du classement tradé : la mesure doit être juste avant d'être lue.

Épinglé :
  1. le score est CELUI de la production (même ordre que `momentum_rank`) ;
  2. il est point-in-time : réécrire le futur ne change aucun score passé ;
  3. un signal planté est détecté (IC > 0, p du test de signe faible) ;
  4. du bruit pur n'est PAS déclaré significatif — ni un facteur commun sans
     information (le défaut de la nulle par permutation, 06/10) ;
  5. pas = horizon → fenêtres disjointes ; sous 12 dates → UNCALIBRATED.
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.research import ic_classement as icc
from tests.backtest.test_preset_diag import Bar

T0 = datetime(2018, 1, 1, tzinfo=UTC)


def _univers(n_titres=40, n_barres=900, persistance=0.0, graine=0) -> dict:
    """Marches aléatoires ; `persistance` > 0 donne à chaque titre une dérive propre,
    donc un momentum passé qui prédit le futur (signal planté)."""
    rng = np.random.default_rng(graine)
    out = {}
    for k in range(n_titres):
        derive = persistance * rng.normal(0, 1)
        r = rng.normal(derive, 0.02, n_barres)
        px = 100 * np.cumprod(1 + r)
        out[f"S{k:02d}"] = [Bar(T0 + timedelta(days=j), *(4 * [float(px[j])]), 1e6)
                            for j in range(n_barres)]
    return out


def test_meme_classement_que_la_production():
    from packages.backtest.preset_config import momentum_rank
    data = _univers(n_titres=30, n_barres=400)
    series = icc._series(data)
    M = {s: c for s, (_, c) in series.items()}
    s0 = 400
    prod = momentum_rank(M, list(M), s0, 12)
    sc = {s: icc.score_momentum(c, s0 - 1) for s, c in M.items()}
    assert prod == sorted(sc, key=lambda s: sc[s], reverse=True)[:12]


def test_point_in_time():
    data = _univers(n_titres=25, n_barres=500)
    futur = {s: b[:400] + [Bar(x.ts, *(4 * [x.close * 3]), 1e6) for x in b[400:]]
             for s, b in data.items()}
    s1, j1 = icc._series(data), "2019-01-28"            # index 392 < 400
    a = icc.coupe(s1, j1, "2019-01-29", "2019-01-30")[1]
    b = icc.coupe(icc._series(futur), j1, "2019-01-29", "2019-01-30")[1]
    assert np.allclose(a, b)


def test_le_label_part_du_prix_d_execution_pas_du_close_du_signal():
    c = np.arange(1.0, 400.0)
    data = {"A": [Bar(T0 + timedelta(days=j), *(4 * [float(c[j])]), 1e6)
                  for j in range(len(c))]}
    jours = [(T0 + timedelta(days=j)).date().isoformat() for j in (300, 301, 306)]
    _, _, fut = icc.coupe(icc._series(data), *jours)
    assert fut[0] == pytest.approx(c[306] / c[301] - 1)        # pas c[306] / c[300]


def test_saut_12_1_lit_un_close_plus_ancien():
    c = np.arange(1.0, 400.0)
    assert icc.score_momentum(c, 300, saut=0) == pytest.approx(c[300] / c[48] - 1)
    assert icc.score_momentum(c, 300, saut=21) == pytest.approx(c[279] / c[48] - 1)
    assert icc.score_momentum(c, 100) is None            # moins de 252 barres


def test_signal_plante_detecte():
    data = _univers(persistance=0.002, graine=1)
    res = icc.mesurer(data, horizons=(20,), n_nulles=100)
    (r,) = res["resultats"]
    assert r["available"] and r["ic_moyen"] > 0.1
    assert r["p_signes"] < 0.05 and r["ecart_top12_moyen"] > 0


def test_bruit_pur_non_significatif():
    res = icc.mesurer(_univers(persistance=0.0, graine=2), horizons=(20,), n_nulles=100)
    (r,) = res["resultats"]
    assert r["available"] and r["p_signes"] > 0.05
    assert abs(r["ic_moyen"]) < r["nulle_p95"] * 1.5


def _univers_facteur(graine: int, n_titres=40, n_barres=1500) -> dict:
    """Un facteur commun (bêtas hétérogènes), AUCUNE information propre au titre :
    le momentum passé ne prédit rien, mais l'IC daté varie fortement d'une date à
    l'autre (signe du facteur passé × signe du facteur futur)."""
    rng = np.random.default_rng(graine)
    beta, f = rng.normal(1.0, 0.6, n_titres), rng.normal(0, 0.015, n_barres)
    out = {}
    for k in range(n_titres):
        px = 100 * np.cumprod(1 + beta[k] * f + rng.normal(0, 0.005, n_barres))
        out[f"S{k:02d}"] = [Bar(T0 + timedelta(days=j), *(4 * [float(px[j])]), 1e6)
                            for j in range(n_barres)]
    return out


def test_facteur_commun_sans_information_non_significatif():
    """Graine 0 : IC +0,095, t = +1,48. L'ancienne nulle (permutation au sein de
    chaque date) rendait p = 0,005 ; le test de signe rend p ≈ 0,14."""
    (r,) = icc.mesurer(_univers_facteur(0), horizons=(20,))["resultats"]
    assert r["available"] and r["p_signes"] > 0.05
    se = r["ic_ecart_type"] / np.sqrt(r["n_dates"])        # la vraie largeur
    assert r["nulle_p95"] == pytest.approx(1.96 * se, rel=0.3)


def test_fenetres_disjointes_et_plancher():
    data = _univers(n_titres=25, n_barres=600)
    res = icc.mesurer(data, horizons=(5, 60), n_nulles=20)
    r5, r60 = res["resultats"]
    assert r5["pas"] == 5 and r5["chevauchement"] is False
    assert r5["n_dates"] == len(range(252, 600 - 5 - 1, 5))
    assert r60["available"] is False and r60["status"] == "UNCALIBRATED"   # 5 dates
    assert res["horizons_testes"] == 2 and res["production"] is True


def test_le_script_ne_consigne_ni_synthetique_ni_uncalibrated(tmp_path, monkeypatch):
    from packages.research import ledger
    from scripts import ic_classement as script
    chemin = tmp_path / "h.jsonl"
    monkeypatch.setattr(ledger, "DEFAULT_PATH", chemin)
    monkeypatch.setattr(ledger.append_record, "__defaults__", (chemin,))
    res = {"resultats": [{"horizon": 5, "available": False},
                         {"horizon": 20, "available": True, "ic_moyen": 0.01,
                          "t_stat": 0.3, "p_signes": 0.7, "n_dates": 40}]}
    assert script._consigner(res, 0, "synthetic") == 0 and not chemin.exists()
    assert script._consigner(res, 0, "réel") == 1
    (rec,) = ledger.read_records(chemin)
    assert rec["facteur"] == "ic_classement:momentum_saut0:h20" and rec["n_essais"] == 1
