"""Grille horizons × stratégies × sorties × fréquences — ce qui doit tenir avant tout chiffre.

  * le stop suiveur (Chandelier) ne recule jamais et n'est connu qu'au close ;
  * une fréquence mensuelle ne décide qu'au DERNIER jour de bourse du mois ;
  * l'état d'une stratégie à t ne dépend que du passé ;
  * une fenêtre d'horizon H exige H années COMPLÈTES — sinon pas de chiffre ;
  * la sortie « tendance » interdit de racheter sous la MM200 (sinon on mesure du churn).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from packages.backtest.signal_long_tp import simuler
from packages.core.models import Bar


def _bars(n=700, graine=0, derive=0.0006):
    rng = np.random.default_rng(graine)
    c = 100 * np.exp(np.cumsum(rng.normal(derive, 0.02, n)))
    o = c * (1 + rng.normal(0, 0.003, n))
    j = [d for d in (date(2018, 1, 1) + timedelta(days=k) for k in range(n * 2))
         if d.weekday() < 5][:n]
    return [Bar("X", "1d", datetime(d.year, d.month, d.day, tzinfo=UTC), o[i],
                max(o[i], c[i]) * 1.01, min(o[i], c[i]) * 0.99, c[i], 1e6)
            for i, d in enumerate(j)]


# ------------------------------------------------------------------ moteur : suiveur

def test_stop_suiveur_cliquet_et_declenchement():
    n = 12
    j = [f"2020-01-{k + 1:02d}" for k in range(n)]
    c = np.array([100, 100, 104, 108, 112, 110, 109, 108, 100, 100, 100, 100], float)
    o = c.copy()
    h, lo = c + 1, c - 1
    lo[8] = 99.0
    long_ = np.zeros(n, bool)
    long_[1] = True
    atr = np.full(n, 2.0)
    r = simuler(j, o, c, long_, np.zeros(n, bool), debut=j[0], cout=0.0, haut=h, bas=lo,
                suiveur=(3.0, atr))
    (t,) = r["trades"]
    # plus haut de clôture 112 (t=4) → stop 112 − 6 = 106 ; touché en t=8 (bas 99)
    assert (t.motif_sortie, t.prix_sortie, t.sortie_jour) == ("stop", 100.0, j[8])


# ------------------------------------------------------------------ fréquences

def test_dates_de_decision():
    from packages.backtest.scenarios_horizons import decisions
    jours = ["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02", "2024-02-05",
             "2024-03-28", "2024-04-01", "2024-12-31", "2025-01-02"]
    assert decisions(jours, "jour").all()
    # dernière séance de chaque période PRÉSENTE dans les données (le calendrier de
    # bourse est connu d'avance : ce n'est pas un regard sur les prix futurs)
    assert decisions(jours, "mois").tolist() == [0, 1, 0, 0, 1, 1, 1, 1, 1]
    # semaines ISO : le 31/12/2024 appartient à la semaine 1 de 2025, comme le 02/01/2025
    assert decisions(jours, "semaine").tolist() == [0, 0, 0, 1, 1, 1, 1, 0, 1]
    assert decisions(jours, "trimestre").tolist() == [0, 0, 0, 0, 0, 1, 1, 1, 1]
    assert decisions(jours, "annee").tolist() == [0, 0, 0, 0, 0, 0, 0, 1, 1]
    with pytest.raises(ValueError):
        decisions(jours, "hebdo")


# ------------------------------------------------------------------ états

@pytest.mark.parametrize("nom", ["smclxtp", "ma_crossover", "tendance_mm200",
                                 "momentum_12_1"])
def test_etats_causaux(nom):
    from packages.backtest.scenarios_horizons import etat
    bars = _bars()
    complet = etat(nom, bars, par_an=252)
    for t in (300, 450, 699):
        np.testing.assert_array_equal(complet[:t + 1], etat(nom, bars[:t + 1], par_an=252))


def test_evenements_en_etat():
    from packages.backtest.scenarios_horizons import depuis_evenements
    long_ = np.array([0, 1, 1, 0, 0, 0, 1, 0], bool)
    flat = np.array([0, 0, 0, 0, 1, 1, 1, 0], bool)
    # long en 1 → vrai ; flat en 4 → faux ; en 6 long ET flat à plat → long
    assert depuis_evenements(long_, flat).tolist() == [0, 1, 1, 1, 0, 0, 1, 1]


def test_sortie_tendance_interdit_le_rachat_sous_la_mm200():
    from packages.backtest.scenarios_horizons import construire
    c = np.array([100.0] * 5)
    sma = np.array([90, 90, 110, 110, 90], float)
    etat_ = np.ones(5, bool)
    dec = np.ones(5, bool)
    s = construire(etat_, dec, c, sma, np.full(5, 2.0), "tendance_mm200", k_tp=3.0)
    assert s["long"].tolist() == [1, 1, 0, 0, 1]          # pas d'achat sous la MM200
    assert s["flat"].tolist() == [0, 0, 1, 1, 0]
    s2 = construire(etat_, dec, c, sma, np.full(5, 2.0), "tp_3atr", k_tp=3.0)
    assert s2["cibles"][0] == pytest.approx(106.0) and not s2["flat"].any()


# ------------------------------------------------------------------ horizons

def test_fenetres_exigent_des_annees_completes():
    from packages.backtest.horizons_stats import fenetres
    jours = [(date(2015, 1, 1) + timedelta(days=k)).isoformat() for k in range(365 * 4)]
    eq = [1.10 ** (k / 365.0) for k in range(len(jours))]          # +10 %/an exactement
    f1 = fenetres(eq, eq, jours, annees=1, pas=30)
    assert f1["n"] > 0 and f1["rend_annuel_median"] == pytest.approx(0.10, abs=1e-3)
    assert f1["part_positive"] == 1.0 and f1["part_bat_bh"] == 0.0     # égal, pas mieux
    assert fenetres(eq, eq, jours, annees=5, pas=30)["n"] == 0          # 4 ans < 5


def test_synthese_par_dimension():
    from packages.backtest.horizons_stats import par_dimension
    lignes = [{"strategie": "a", "sortie": "x", "frequence": "jour", "sharpe": 1.0},
              {"strategie": "a", "sortie": "y", "frequence": "mois", "sharpe": 3.0},
              {"strategie": "b", "sortie": "x", "frequence": "jour", "sharpe": -1.0}]
    d = par_dimension(lignes, "sharpe")
    assert d["strategie"]["a"] == pytest.approx(2.0) and d["strategie"]["b"] == -1.0
    assert d["frequence"]["jour"] == pytest.approx(0.0)
