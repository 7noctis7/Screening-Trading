"""Tests perf_summary — source unique de vérité des métriques (hors-ligne)."""

import numpy as np

from packages.portfolio.metrics import perf_summary, sharpe


def test_perf_summary_complete_and_consistent():
    rng = np.random.default_rng(0)
    r = rng.normal(0.0004, 0.01, 500)
    out = perf_summary(r)
    assert out["available"] and out["n"] == 500
    for k in ("total_return", "cagr", "vol", "sharpe", "sortino", "calmar",
              "max_drawdown"):
        assert k in out
    # cohérence : même Sharpe que la fonction equity-based sur la même série
    eq = (1 + np.asarray(r)).cumprod()
    assert abs(out["sharpe"] - round(sharpe(eq.tolist()), 3)) < 0.02
    assert out["max_drawdown"] <= 0.0


def test_perf_summary_with_pnls_profit_factor():
    r = [0.01, -0.005, 0.02, -0.01, 0.015] * 5
    out = perf_summary(r, pnls=[300.0, -50.0])
    assert out["profit_factor"] == 6.0 and out["win_rate"] == 0.5


def test_perf_summary_drops_nan_and_guards_short():
    assert perf_summary([0.01])["available"] is False
    out = perf_summary([0.01, float("nan"), 0.02, -0.01])
    assert out["available"] and out["n"] == 3        # NaN retiré
