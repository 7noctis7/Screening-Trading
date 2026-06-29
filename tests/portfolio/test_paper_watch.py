"""Tests watchdog de dérive paper vs backtest (déterministe, hors-ligne)."""

import numpy as np

from packages.portfolio.paper_watch import drift_report


def _equity(daily_mu, sigma, n, seed):
    r = np.random.default_rng(seed).normal(daily_mu, sigma, n)
    return list(100 * np.cumprod(1 + r))


def test_no_drift_when_paper_matches_backtest():
    eq = _equity(0.001, 0.008, 120, 0)                 # tendance saine
    ref = {"sharpe": 1.5, "max_drawdown": -0.20}
    out = drift_report(eq, ref)
    assert out["available"] and out["drift"] is False and out["alerts"] == []


def test_drift_on_sharpe_collapse():
    eq = _equity(-0.0008, 0.02, 120, 1)                # paper décroche
    ref = {"sharpe": 2.35, "max_drawdown": -0.05}
    out = drift_report(eq, ref, sharpe_drop=1.0)
    assert out["drift"] is True and any("Sharpe" in a for a in out["alerts"])


def test_drift_on_deeper_drawdown():
    eq = [100, 102, 104, 70] + [70] * 40               # krach → DD ~-33%
    ref = {"sharpe": -99, "max_drawdown": -0.05}        # neutralise l'alerte Sharpe
    out = drift_report(eq, ref, dd_buffer=0.05, min_obs=20)
    assert out["drift"] is True and any("MaxDD" in a for a in out["alerts"])


def test_too_short_is_not_available():
    out = drift_report([100, 101, 102], {"sharpe": 2.0})
    assert out["available"] is False and out["n"] == 2
