import numpy as np
from packages.portfolio.optimize import inverse_variance_weights, min_variance_weights, hrp_weights


def _cov():
    return [[0.04, 0.005, 0.0], [0.005, 0.09, 0.0], [0.0, 0.0, 0.16]]


def test_weights_sum_to_one_and_nonneg():
    for fn in (inverse_variance_weights, min_variance_weights, hrp_weights):
        w = fn(_cov())
        assert abs(sum(w) - 1.0) < 1e-6
        assert all(x >= -1e-9 for x in w)


def test_ivp_favors_low_variance():
    w = inverse_variance_weights(_cov())
    assert w[0] > w[2]              # variance 0.04 < 0.16 → poids plus élevé


def test_single_asset():
    assert hrp_weights([[0.04]]) == [1.0]


def test_erc_weights_valid():
    from packages.portfolio.optimize import equal_risk_contribution
    w = equal_risk_contribution([[0.04, 0.0, 0.0], [0.0, 0.09, 0.0], [0.0, 0.0, 0.16]])
    assert abs(sum(w) - 1.0) < 1e-6 and all(x > 0 for x in w)
    assert w[0] > w[2]      # actif moins risqué → plus de poids (parité du risque)
