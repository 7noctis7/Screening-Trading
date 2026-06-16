import numpy as np
from packages.portfolio import risk_metrics as R


def test_var_cvar_positive_and_ordered():
    r = np.random.default_rng(0).normal(0, 0.02, 1000)
    var = R.var_historical(r, 0.95)
    cvar = R.cvar_historical(r, 0.95)
    assert var > 0 and cvar >= var          # la perte moyenne de queue ≥ VaR


def test_var_empty_is_zero():
    assert R.var_historical([], 0.95) == 0.0
