"""Fixes audit 07/17 : fill t+1 (M-1), sabotage sur Δposition (M-2), delta survivorship (XL-1).

Données synthétiques (autorisé : valider la MATH, pas calibrer). numpy/stdlib.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from packages.backtest.preset_backtest import preset_backtest
from packages.backtest.survivorship_delta import survivorship_delta
from packages.research.adversarial import sabotage_verdict, stress_returns


@dataclass
class Bar:
    ts: datetime
    close: float


def _series(n: int, drift: float, vol: float, seed: int) -> list[Bar]:
    import random
    rng = random.Random(seed)
    px, out, t0 = 100.0, [], datetime(2020, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        px *= math.exp(drift / 252 + vol / math.sqrt(252) * rng.gauss(0, 1))
        out.append(Bar(t0 + timedelta(days=i), px))
    return out


def _data(n=400, k=12):
    return {f"S{i}": _series(n, 0.02 + 0.03 * (i % 6), 0.18 + 0.02 * (i % 4), seed=i)
            for i in range(k)}


# ---------------- M-1 : fill t+1 -----------------------------------------------
def test_exec_lag_defaut_inchange():
    """exec_lag=0 (défaut) = comportement historique EXACT (non-régression)."""
    data = _data()
    a = preset_backtest(data, top_k=8)
    b = preset_backtest(data, top_k=8, exec_lag=0)
    assert a["preset"]["sharpe"] == b["preset"]["sharpe"]


def test_exec_lag_1_modifie_le_resultat():
    """exec_lag=1 (fill au close t+1) change le résultat → le mini look-ahead existait bien
    et est désormais mesurable (make preset-lab chiffre l'écart)."""
    data = _data()
    base = preset_backtest(data, top_k=8, exec_lag=0)
    lag1 = preset_backtest(data, top_k=8, exec_lag=1)
    assert base.get("available") and lag1.get("available")
    assert base["preset"]["sharpe"] != lag1["preset"]["sharpe"]   # décalage réel d'exécution


# ---------------- M-2 : sabotage sur Δposition --------------------------------
def test_sabotage_turnover_moins_severe_que_par_barre():
    """Coût sur le Δposition (turnover < 1/barre) doit AMPUTER MOINS qu'un coût à chaque barre."""
    rng = np.random.default_rng(0)
    rets = 0.0004 + rng.normal(0, 0.01, 500)                      # edge positif
    per_bar = stress_returns(rets, extra_cost_bps=30, noise_mult=0, latency=0)
    on_turn = stress_returns(rets, extra_cost_bps=30, noise_mult=0, latency=0, turnover=0.1)
    assert on_turn.mean() > per_bar.mean()                        # moins de coût → rendement moins amputé


def test_sabotage_turnover_zero_aucun_cout():
    rets = np.full(300, 0.001)
    out = stress_returns(rets, extra_cost_bps=50, noise_mult=0, latency=0, turnover=0.0)
    assert np.allclose(out, rets)                                 # 0 turnover → 0 coût


def test_sabotage_verdict_accepte_turnover():
    rng = np.random.default_rng(1)
    rets = 0.0006 + rng.normal(0, 0.008, 400)
    flat = sabotage_verdict(rets, extra_cost_bps=30)
    turn = sabotage_verdict(rets, extra_cost_bps=30, turnover=0.05)
    assert flat["available"] and turn["available"]
    assert turn["sharpe_retention"] >= flat["sharpe_retention"]   # moins pénalisé → meilleure rétention


# ---------------- XL-1 : delta de survivorship --------------------------------
def test_survivorship_delta_sans_prix_delistes():
    """delisted.csv n'a pas les prix → delta indisponible AVEC message explicite (jamais inventé)."""
    out = survivorship_delta(_data(), delisted_data=None, top_k=8)
    assert out["available"] is False and "ingest-delisted" in out["reason"]


def test_survivorship_delta_avec_prix_delistes():
    """Avec des prix de délistés fournis, le delta est calculé et structuré."""
    surv = _data(k=10)
    delisted = {f"D{i}": _series(400, -0.10, 0.30, seed=100 + i) for i in range(4)}  # perdants
    out = survivorship_delta(surv, delisted_data=delisted, top_k=8)
    assert out["available"] and out["corrected"]
    assert out["n_delisted"] == 4
    assert set(out["delta"]) == {"sharpe", "annualized", "max_drawdown", "total_return"}
