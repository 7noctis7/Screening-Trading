"""satellite_smc — SMCLXTP-A à la place du satellite : causalité, pondération, règle."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np

from packages.core.models import Bar


def _serie(sym, graine, n=700):
    rng = np.random.default_rng(graine)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.02, n)))
    j = [d for d in (date(2018, 1, 1) + timedelta(days=k) for k in range(n * 2))
         if d.weekday() < 5][:n]
    return [Bar(sym, "1d", datetime(d.year, d.month, d.day, tzinfo=UTC), c[i] * 0.999,
                c[i] * 1.01, c[i] * 0.99, c[i], 1e6) for i, d in enumerate(j)]


def _univers():
    return {s: _serie(s, g) for g, s in enumerate(["QQQ", "A", "B", "C", "D"])}


def test_poids_equiponderes_et_causaux():
    """Les poids du jour j sont identiques que l'avenir soit connu ou non."""
    from packages.backtest.panel import _jour
    from packages.backtest.preset_rejeu import tronquer
    from packages.backtest.satellite_smc import etats_smc, poids_smc
    data = _univers()
    complet = etats_smc(data)
    jours = [_jour(b) for b in data["A"]][300::37]
    vus = 0
    for j in jours:
        w = poids_smc(complet, j)
        assert w == poids_smc(etats_smc(tronquer(data, j)), j)
        if w:
            vus += 1
            assert abs(sum(w.values()) - 1.0) < 1e-12 and len(set(w.values())) == 1
    assert vus > 0


def test_regle_pre_enregistree():
    from packages.backtest.satellite_smc import verdict
    meilleur = {"disponible": True, "verdict": "meilleur"}
    assert verdict(meilleur, -0.20, -0.25).startswith("SMCLXTP-A MEILLEUR")
    assert verdict(meilleur, -0.30, -0.25) == "PRODUCTION CONSERVÉE"     # DD pire
    assert verdict({"disponible": True, "verdict": "indiscernable"}, -0.1, -0.3) \
        == "PRODUCTION CONSERVÉE"
    assert verdict({"disponible": False}, 0, 0).startswith("INDÉTERMINÉ")


def test_comparaison_memes_dates_meme_coeur():
    """Les deux portefeuilles partagent calendrier et cœur : seul le satellite change."""
    from packages.backtest.preset_rejeu import avec_coeur, calendrier
    from packages.backtest.satellite_smc import comparer_satellites
    data = _univers()
    cal = calendrier(data)
    jours = cal[260::5]
    brutes = [(j, {"A": 0.5, "B": 0.5}) for j in jours]
    coeur = {"QQQ": 0.5}
    prep = (cal, brutes, [(j, avec_coeur(w, coeur)) for j, w in brutes])
    res = comparer_satellites(data, prep, coeur=coeur, classes={})
    assert res["available"] and res["delta"]["disponible"]
    assert res["n_ordres"]["smclxtp"] > 0 and res["titres_long_moyen"] > 0
    assert set(res["stats"]) == {"production", "smclxtp"}
    assert res["verdict"] in ("PRODUCTION CONSERVÉE",
                              "SMCLXTP-A MEILLEUR (décision explicite requise)")
