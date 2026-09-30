"""Backtest « long au signal, sortie au signal TP » — les règles d'exécution d'abord.

Un signal naît au CLOSE de la barre t (c'est là qu'un pivot est confirmé) : l'ordre part
à l'OUVERTURE de t+1. Une position à la fois, pas de pyramide, frais à chaque jambe, une
position ouverte en fin de période n'est pas un trade clôturé.
"""

from __future__ import annotations

import numpy as np
import pytest

from packages.backtest.signal_long_tp import kpis, simuler


def _jours(n):
    return [f"2020-{1 + k // 28:02d}-{1 + k % 28:02d}" for k in range(n)]


def _cas(n=10, ouvertures=None, clotures=None):
    o = np.full(n, 100.0) if ouvertures is None else np.asarray(ouvertures, float)
    c = np.full(n, 100.0) if clotures is None else np.asarray(clotures, float)
    return _jours(n), o, c


def _sig(n, *idx):
    s = np.zeros(n, bool)
    s[list(idx)] = True
    return s


def test_entree_et_sortie_a_l_ouverture_suivante_avec_frais():
    j, o, c = _cas(ouvertures=[100, 100, 100, 101, 102, 110, 111, 111, 111, 111])
    r = simuler(j, o, c, _sig(10, 1), _sig(10, 4), debut=j[0], cout=0.0005)
    (t,) = r["trades"]
    assert (t.entree_jour, t.sortie_jour) == (j[2], j[5])        # t+1, jamais t
    parts = 10_000 / (100 * 1.0005)
    assert t.pnl == pytest.approx(parts * 110 * (1 - 0.0005) - 10_000)
    assert t.pnl_pct == pytest.approx(110 * 0.9995 / (100 * 1.0005) - 1)


def test_pas_de_pyramide_et_tp_a_plat_ignore():
    j, o, c = _cas()
    r = simuler(j, o, c, _sig(10, 1, 2, 3), _sig(10, 0, 6), debut=j[0], cout=0.0)
    assert len(r["trades"]) == 1                     # TP en 0 : à plat, ignoré
    assert r["trades"][0].entree_jour == j[2]        # longs en 2 et 3 : déjà investi


def test_meme_barre_long_et_tp():
    j, o, c = _cas()
    r = simuler(j, o, c, _sig(10, 1, 4), _sig(10, 4), debut=j[0], cout=0.0)
    # à plat en 1 → entrée ; en 4 (long ET tp) on est investi → sortie, pas de ré-entrée
    assert len(r["trades"]) == 1 and r["trades"][0].sortie_jour == j[5]


def test_signaux_avant_le_debut_ignores():
    j, o, c = _cas()
    r = simuler(j, o, c, _sig(10, 1, 6), _sig(10, 8), debut=j[5], cout=0.0)
    assert [t.entree_jour for t in r["trades"]] == [j[7]]
    assert r["dates"][0] == j[5]


def test_position_ouverte_en_fin_n_est_pas_un_trade_cloture():
    j, o, c = _cas(clotures=[100] * 5 + [120] * 5)
    r = simuler(j, o, c, _sig(10, 2), _sig(10), debut=j[0], cout=0.0)
    assert r["trades"] == [] and r["ouvert"] is not None
    assert r["equity"][-1] == pytest.approx(10_000 * 120 / 100)   # marquée au close


def test_l_avenir_ne_change_pas_les_trades_passes():
    rng = np.random.default_rng(0)
    n = 200
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    o = c * (1 + rng.normal(0, 0.003, n))
    lg, tp = rng.random(n) < 0.05, rng.random(n) < 0.05
    j = _jours(n)
    complet = simuler(j, o, c, lg, tp, debut=j[0], cout=0.0005)
    k = 120
    tronque = simuler(j[:k], o[:k], c[:k], lg[:k], tp[:k], debut=j[0], cout=0.0005)
    assert complet["equity"][:k - 1] == pytest.approx(tronque["equity"][:k - 1])
    fermes = [t for t in complet["trades"] if t.sortie_jour < j[k - 1]]
    assert fermes == tronque["trades"][:len(fermes)]


def test_kpis():
    j, o, c = _cas(n=12, ouvertures=[100, 100, 100, 110, 110, 90, 90, 90, 100, 100, 100, 100])
    r = simuler(j, o, c, _sig(12, 1, 5), _sig(12, 2, 7), debut=j[0], cout=0.0)
    k = kpis(r, par_an=252)
    # trade 1 : 100 → 110 (+10 %), trade 2 : 90 → 100 (+11,1 %) — tous gagnants
    assert k["trades"] == 2 and k["win_rate"] == 1.0
    assert k["pnl_moyen_pct"] == pytest.approx((0.10 + 100 / 90 - 1) / 2)
    assert k["duree_moyenne_jours"] == pytest.approx(((3 - 2) + (8 - 6)) / 2)
    assert k["max_drawdown"] <= 0.0 and np.isfinite(k["sharpe"])
    assert set(k) >= {"profit_factor", "payoff", "sortino", "cagr", "pnl_moyen",
                      "exposition", "buy_and_hold"}
