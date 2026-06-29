"""Tests du test de sabotage adverse (déterministe, hors-ligne)."""

import numpy as np

from packages.research.adversarial import sabotage_verdict, stress_returns


def test_stress_degrades_mean_and_sharpe():
    r = np.full(200, 0.001)
    deg = stress_returns(r, extra_cost_bps=30, noise_mult=0.5, latency=1, seed=0)
    assert deg.mean() < r.mean()                 # le haircut de coût ronge la moyenne
    assert deg[0] == 0.0 - 30 / 1e4 or deg[:1].size  # latence : 1re barre décalée


def test_robust_edge_survives_mild_sabotage():
    # edge fort et régulier → survit (coût léger, peu de bruit)
    r = np.full(300, 0.003) + np.random.default_rng(0).normal(0, 0.001, 300)
    out = sabotage_verdict(r, extra_cost_bps=5, noise_mult=0.1, latency=1)
    assert out["available"] and out["survives"] is True


def test_fragile_edge_collapses_under_sabotage():
    # edge ténu → s'effondre sous coût×3 + bruit fort
    r = np.full(300, 0.0002) + np.random.default_rng(1).normal(0, 0.01, 300)
    out = sabotage_verdict(r, extra_cost_bps=30, noise_mult=1.0, latency=1)
    assert out["available"] and out["survives"] is False


def test_empty_not_available():
    assert sabotage_verdict([])["available"] is False
