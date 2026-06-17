import numpy as np
from packages.portfolio.risk_advanced import ewma_vol, cornish_fisher_var, component_var


def test_ewma_vol_positive():
    rng = np.random.default_rng(0)
    assert ewma_vol(rng.normal(0, 0.01, 300)) > 0


def test_cornish_fisher_positive_and_scales_with_vol():
    rng = np.random.default_rng(1)
    low = rng.normal(0, 0.01, 1000)
    high = rng.normal(0, 0.03, 1000)
    assert cornish_fisher_var(low) >= 0
    assert cornish_fisher_var(high) > cornish_fisher_var(low)   # plus de vol → plus de VaR


def test_component_var_sums_to_portfolio():
    cov = [[0.04, 0.01], [0.01, 0.09]]
    r = component_var([0.5, 0.5], cov)
    assert abs(sum(r["component"]) - r["portfolio_var"]) < 1e-6
