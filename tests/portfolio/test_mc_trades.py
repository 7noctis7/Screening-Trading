"""Tests Monte Carlo par séquences de trades (drawdown path-dependent)."""

import numpy as np

from packages.portfolio.stress import monte_carlo_trades


def test_too_few_trades():
    assert monte_carlo_trades([0.01])["available"] is False


def test_shuffle_preserves_final_return():
    # une permutation ne change PAS le rendement composé final (produit commutatif)
    trades = [0.05, -0.02, 0.03, -0.04, 0.06]
    out = monte_carlo_trades(trades, n_sims=200, mode="shuffle", seed=1)
    expected = float(np.prod([1 + t for t in trades]) - 1)
    # median_return est arrondi à 4 décimales → tolérance cohérente
    assert out["available"] and abs(out["median_return"] - expected) < 1e-3


def test_shuffle_varies_drawdown():
    # …mais l'ORDRE change le drawdown → la distribution des DD n'est pas dégénérée
    trades = [0.05, -0.02, 0.03, -0.04, 0.06, -0.08, 0.02]
    out = monte_carlo_trades(trades, n_sims=500, mode="shuffle", seed=2)
    assert out["worst_dd"] <= out["median_dd"] <= 0.0      # DD signés (≤ 0)
    assert out["worst_dd"] < out["dd_p95"] + 1e-9          # pire cas ≤ p95


def test_bootstrap_mode_runs_and_flags_ruin():
    losers = [-0.3, -0.25, -0.2, 0.05, -0.4]      # série perdante → ruine plausible
    out = monte_carlo_trades(losers, n_sims=500, mode="bootstrap",
                             ruin_threshold=-0.5, seed=3)
    assert out["available"] and 0.0 <= out["p_ruin"] <= 1.0
    assert out["n_trades"] == 5
