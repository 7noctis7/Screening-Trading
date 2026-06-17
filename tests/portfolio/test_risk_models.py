import numpy as np
from packages.portfolio.garch import fit_garch
from packages.portfolio.var_backtest import backtest_var, kupiec_pof
from packages.portfolio.factor_risk import pca_risk


def test_garch_fits_and_forecasts():
    rng = np.random.default_rng(0)
    # série avec clustering de vol (régimes)
    r = np.concatenate([rng.normal(0, 0.005, 300), rng.normal(0, 0.03, 300)])
    g = fit_garch(r)
    assert g["available"] and g["forecast_vol"] > 0
    assert 0 < g["persistence"] < 1.0


def test_garch_too_short():
    assert fit_garch([0.01, -0.01])["available"] is False


def test_kupiec_pass_when_breaches_match():
    # 5% de 1000 = ~50 dépassements attendus → doit passer
    r = kupiec_pof(1000, 50, alpha=0.95)
    assert r["pass"] and r["p_value"] > 0.05


def test_kupiec_fail_when_too_many_breaches():
    r = kupiec_pof(1000, 150, alpha=0.95)
    assert not r["pass"]


def test_backtest_var_counts_breaches():
    rets = [-0.2, 0.01, -0.005, -0.3, 0.02]
    r = backtest_var(rets, var=0.1, alpha=0.95)
    assert r["breaches"] == 2


def test_pca_risk_systematic():
    rng = np.random.default_rng(1)
    common = rng.normal(0, 0.02, 200)
    data = {f"A{i}": (common + rng.normal(0, 0.002, 200)).tolist() for i in range(4)}
    r = pca_risk(data)
    assert r["available"] and r["systematic_pct"] > 0.7   # 1 facteur commun domine
