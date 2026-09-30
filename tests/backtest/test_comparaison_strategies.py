"""Comparaison SMCLXTP-A ↔ stratégies du bot : mêmes barres, même moteur, mêmes frais.

Ce que ces tests verrouillent : chaque stratégie ne voit que le passé (les signaux à t ne
changent pas si l'avenir change) ; une stratégie sans réglages connus est écartée et DITE
UNCALIBRATED, jamais lancée avec des valeurs inventées ; le tirage « aléatoire » des actifs
est reproductible (graine) et fixé avant de regarder les résultats.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.backtest.comparaison_strategies import (
    STRATEGIES,
    comparer,
    non_calibrees,
    signaux,
    synthese,
    tirage,
)
from packages.core.models import Bar


def _bars(n=500, graine=0, sym="X"):
    rng = np.random.default_rng(graine)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.02, n)))
    o = c * (1 + rng.normal(0, 0.003, n))
    d0 = datetime(2019, 6, 3, tzinfo=UTC)
    return [Bar(sym, "1d", d0 + timedelta(days=i), o[i], max(o[i], c[i]) * 1.01,
                min(o[i], c[i]) * 0.99, c[i], 1e6) for i in range(n)]


def test_strategies_comparees_et_ecartees():
    assert STRATEGIES == ("smclxtp", "ma_crossover", "rsi_reversion", "swing")
    assert "institutional_price_action" in non_calibrees()


@pytest.mark.parametrize("nom", STRATEGIES)
def test_signaux_causaux(nom):
    bars = _bars()
    complet = signaux(nom, bars)
    t = 380
    tronque = signaux(nom, bars[:t + 1])
    for cle in ("long", "flat"):
        np.testing.assert_array_equal(complet[cle][:t + 1], tronque[cle], err_msg=cle)
    np.testing.assert_allclose(complet["stops"][:t + 1], tronque["stops"], equal_nan=True)


def test_comparaison_et_synthese():
    univers = {f"S{k}": _bars(graine=k, sym=f"S{k}") for k in range(3)}
    res = comparer(univers, debut="2019-10-01", classes={}, par_an=252)
    assert set(res) == set(univers)
    for par_strat in res.values():
        assert set(par_strat) == set(STRATEGIES) | {"buy_and_hold"}
    s = synthese(res)
    assert set(s) == set(STRATEGIES) | {"buy_and_hold"}
    assert {"sharpe_median", "cagr_median", "maxdd_median", "trades_total",
            "win_rate_global"} <= set(s["smclxtp"])


def test_tirage_reproductible_et_fixe_avant_les_resultats():
    candidats = [f"T{k}" for k in range(50)]
    a = tirage(candidats, 6, graine=20260930)
    assert a == tirage(list(reversed(candidats)), 6, graine=20260930)   # ordre indifférent
    assert len(a) == 6 and len(set(a)) == 6 and set(a) <= set(candidats)
    assert a != tirage(candidats, 6, graine=1)
