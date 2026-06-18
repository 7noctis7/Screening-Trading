"""Black-Litterman, régime de volatilité, audit biais du survivant."""

import numpy as np

from packages.data.survivorship import survivorship_audit
from packages.portfolio.black_litterman import black_litterman, views_from_scores
from packages.regime.vol_regime import vol_regime


def _cov(n=4, seed=0):
    rng = np.random.default_rng(seed)
    a = rng.normal(0, 1, size=(200, n))
    return np.cov(a, rowvar=False)


def test_bl_no_views_returns_prior_and_valid_weights():
    cov = _cov()
    wm = np.array([0.25, 0.25, 0.25, 0.25])
    res = black_litterman(cov, wm, np.zeros((0, 4)), np.zeros(0))
    assert abs(sum(res["weights"]) - 1.0) < 1e-2          # tolérance arrondi 4 décimales
    assert res["posterior_returns"] == res["prior_returns"]   # sans vue → postérieur = prior


def test_bl_views_tilt_weights():
    cov = _cov()
    wm = np.array([0.25, 0.25, 0.25, 0.25])
    P, Q = views_from_scores([2.0, 0.0, 0.0, -2.0])           # vue haussière #0, baissière #3
    res = black_litterman(cov, wm, P, Q)
    w = res["weights"]
    assert abs(sum(w) - 1.0) < 1e-2
    assert all(x >= 0 for x in w)                              # long-only


def test_vol_regime_classifies():
    rng = np.random.default_rng(1)
    rets = rng.normal(0, 0.01, size=400)
    r = vol_regime(rets, window=20)
    assert r["available"]
    assert r["state"] in {"calme", "normal", "stress"}
    assert 0.0 < r["exposure_multiplier"] <= 1.0


def test_survivorship_audit_flags_uncorrected():
    a = survivorship_audit(["AAPL", "MSFT", "GOOG"], delisted=[])
    assert a["corrected"] is False and a["n_active"] == 3
    b = survivorship_audit(["AAPL"], delisted=[{"symbol": "LEH"}])
    assert b["corrected"] is True and b["n_delisted"] == 1
