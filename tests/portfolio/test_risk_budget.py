import numpy as np
from packages.portfolio.risk_budget import risk_contributions, covariance


def test_contributions_sum_to_one():
    cov = [[0.04, 0.0], [0.0, 0.09]]
    r = risk_contributions([0.5, 0.5], cov)
    assert abs(sum(r["contrib_pct"]) - 1.0) < 1e-6
    assert r["portfolio_vol"] > 0


def test_higher_vol_asset_contributes_more():
    cov = [[0.01, 0.0], [0.0, 0.25]]
    r = risk_contributions([0.5, 0.5], cov)
    assert r["contrib_pct"][1] > r["contrib_pct"][0]


def test_diversification_ratio_ge_one_uncorrelated():
    cov = [[0.04, 0.0], [0.0, 0.04]]
    r = risk_contributions([0.5, 0.5], cov)
    assert r["diversification_ratio"] >= 1.0


def test_covariance_shape():
    syms, cov = covariance({"A": [0.01, -0.02, 0.03, 0.0], "B": [0.0, 0.01, -0.01, 0.02]})
    assert syms == ["A", "B"] and cov.shape == (2, 2)


def test_empty():
    r = risk_contributions([], [])
    assert r["portfolio_vol"] == 0.0
