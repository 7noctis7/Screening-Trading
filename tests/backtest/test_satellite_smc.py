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


def test_top_k_par_momentum():
    """Seuls les `top_k` titres acheteurs au plus fort momentum 12-1 sont retenus."""
    from packages.backtest.satellite_smc import poids_smc
    j = [f"2020-{m:02d}-{d:02d}" for m in range(1, 13) for d in range(1, 29)][:300]
    oui = np.ones(300, bool)
    etats = {s: (j, oui, np.linspace(100, 100 * f, 300))
             for s, f in (("A", 1.1), ("B", 3.0), ("C", 2.0), ("D", 0.5))}
    etats["E"] = (j, np.zeros(300, bool), np.linspace(100, 900, 300))   # pas acheteur
    assert poids_smc(etats, j[-1], top_k=2) == {"B": 0.5, "C": 0.5}


def test_satellite_non_construit_invalide():
    """Le défaut du premier passage : un satellite presque vide ne juge rien."""
    from packages.backtest.satellite_smc import verdict
    meilleur = {"disponible": True, "verdict": "meilleur"}
    assert verdict(meilleur, -0.1, -0.3, remplissage=0.05).startswith("INVALIDE")


def test_exposition_hors_coeur_mesuree():
    from packages.backtest.preset_rejeu import avec_coeur, calendrier
    from packages.backtest.satellite_smc import comparer_satellites
    data = _univers()
    cal = calendrier(data)
    brutes = [(j, {"A": 0.5, "B": 0.5}) for j in cal[260::5]]
    coeur = {"QQQ": 0.5}
    res = comparer_satellites(data, (cal, brutes, [(j, avec_coeur(w, coeur))
                                                   for j, w in brutes]),
                              coeur=coeur, classes={})
    assert 0.3 < res["exposition_satellite"]["production"] <= 0.55
    assert 0.0 < res["remplissage"] <= 1.1
