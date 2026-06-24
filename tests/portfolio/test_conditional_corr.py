"""Tests corrélation conditionnelle (fausse diversification) + kill-switch intraday."""

import numpy as np

from packages.portfolio.correlation import conditional_correlation
from packages.portfolio.stress import drawdown_breach


def test_conditional_corr_detects_breakdown():
    # 2 actifs décorrélés en calme mais qui plongent ENSEMBLE quand le marché chute
    rng = np.random.default_rng(0)
    n = 400
    market = rng.standard_normal(n)
    a = rng.standard_normal(n)
    b = rng.standard_normal(n)
    crash = market <= np.quantile(market, 0.2)
    a[crash] = market[crash] * 3        # en stress, a et b suivent le marché → corrélés
    b[crash] = market[crash] * 3
    out = conditional_correlation({"A": list(a), "B": list(b)}, list(market))
    assert out["available"]
    assert out["avg_corr_stress"] > out["avg_corr_calm"]
    assert out["diversification_breakdown"] is True


def test_conditional_corr_stable_when_truly_diversified():
    rng = np.random.default_rng(1)
    n = 400
    market = list(rng.standard_normal(n))
    a = list(rng.standard_normal(n))
    b = list(rng.standard_normal(n))      # indépendants en tout régime
    out = conditional_correlation({"A": a, "B": b}, market)
    assert out["available"] and out["diversification_breakdown"] is False


def test_conditional_corr_needs_data():
    assert conditional_correlation({"A": [1, 2]}, [1, 2])["available"] is False


def test_drawdown_breach_triggers():
    eq = [100, 110, 120, 100, 95]          # pic 120 → -20.8% → breach à -15%
    out = drawdown_breach(eq, dd_limit=-0.15)
    assert out["available"] and out["breach"] is True
    assert out["drawdown"] < -0.15


def test_drawdown_no_breach_when_shallow():
    out = drawdown_breach([100, 110, 108], dd_limit=-0.15)
    assert out["available"] and out["breach"] is False
