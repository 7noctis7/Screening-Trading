"""Adaptateur vectorbt — le repli numpy doit donner un résultat correct sans vectorbt."""

from __future__ import annotations

from packages.backtest.vectorbt_adapter import quick_backtest


def test_repli_numpy_long_only():
    closes = [100, 110, 121, 121]
    entries = [True, False, False, False]
    exits = [False, False, True, False]
    r = quick_backtest(closes, entries, exits, fees=0.0)
    # entrée à 100 (i0), détenu jusqu'à la sortie i2 (121) → +21 %
    assert r["n_trades"] == 1
    assert abs(r["total_return"] - 0.21) < 1e-6
    assert r["engine"] in ("vectorbt", "numpy (repli)")


def test_entree_unique_compte_un_trade():
    closes = [10, 9, 11, 12]
    r = quick_backtest(closes, [False, True, False, False], [False, False, False, True], fees=0.0)
    assert r["n_trades"] == 1


def test_serie_trop_courte():
    assert quick_backtest([100], [True], [False])["n_trades"] == 0
