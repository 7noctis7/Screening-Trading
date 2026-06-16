import numpy as np
from packages.portfolio import correlation as C, stress as S
from packages.portfolio.attribution import attribute
from packages.portfolio.review import expert_review


def test_clustering_groups_correlated():
    rng = np.random.default_rng(0); base = rng.normal(0, 0.01, 300)
    rets = {"A": list(base + rng.normal(0, 0.0005, 300)),
            "B": list(base + rng.normal(0, 0.0005, 300)),
            "Z": list(rng.normal(0, 0.01, 300))}
    syms, corr = C.correlation_matrix(rets)
    groups = C.cluster(syms, corr, 0.7)
    in_same = any({"A", "B"}.issubset(set(g)) for g in groups)
    z_alone = any(g == ["Z"] for g in groups)
    assert in_same and z_alone


def test_attribution_sums_pnl():
    from types import SimpleNamespace
    trades = [SimpleNamespace(strategy="ma", pnl_net=10.0),
              SimpleNamespace(strategy="ma", pnl_net=-3.0),
              SimpleNamespace(strategy="rsi", pnl_net=5.0)]
    out = attribute(trades, "strategy")
    assert out["ma"] == 7.0 and out["rsi"] == 5.0


def test_monte_carlo_reproducible_and_bounded():
    r = np.random.default_rng(0).normal(0.0005, 0.01, 300)
    a = S.monte_carlo(r, horizon=60, n_sims=200, seed=1)
    b = S.monte_carlo(r, horizon=60, n_sims=200, seed=1)
    assert a == b                            # seedé → reproductible
    assert 0.0 <= a["p_ruin"] <= 1.0


def test_scenario_loss_via_beta():
    assert S.scenario_loss(100_000, -0.20, beta=1.5) == -30_000.0


def test_review_is_anchored_and_scored():
    rev = expert_review({"sharpe": 1.4, "max_drawdown": -0.08, "beta": 1.4, "p_ruin": 0.08})
    assert 0 <= rev.health_score <= 100
    assert any("1.4" in s for s in rev.strengths)          # cite le Sharpe réel
    assert any("ruine" in r.lower() for r in rev.risks)    # risque détecté
    assert rev.recommendations                              # au moins une reco
