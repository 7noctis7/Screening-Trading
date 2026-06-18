"""Volatilité gérée (Moreira-Muir) + adaptateur skfolio (optionnel)."""

import numpy as np
import pytest

from packages.portfolio.skfolio_adapter import skfolio_available, skfolio_weights
from packages.portfolio.vol_managed import (realized_vol, vol_managed_backtest,
                                            volatility_managed)


def _rets_with_vol_clusters(n=600, seed=7):
    rng = np.random.default_rng(seed)
    out, vol = [], 0.01
    for _ in range(n):
        vol = 0.9 * vol + 0.1 * (0.03 if rng.random() < 0.05 else 0.008)   # clustering
        out.append(rng.normal(0.0004, vol))
    return np.array(out)


def test_realized_vol_shape_and_positive():
    r = _rets_with_vol_clusters()
    rv = realized_vol(r, window=20)
    assert len(rv) == len(r)
    assert np.nanmin(rv) >= 0.0


def test_no_leverage_cap():
    r = _rets_with_vol_clusters()
    vm = volatility_managed(r, target_vol=0.15, max_leverage=1.0)
    assert vm["exposure"].max() <= 1.0 + 1e-9          # jamais de levier
    assert vm["exposure"].min() >= 0.0


def test_vol_managed_targets_vol_on_clustered_data():
    r = _rets_with_vol_clusters()
    res = vol_managed_backtest(r, target_vol=0.12, window=20, max_leverage=1.0)
    assert res["available"]
    # la vol gérée doit être plus proche (ou en-dessous) de la cible que la brute si brute > cible
    assert res["managed"]["vol"] <= res["raw"]["vol"] + 1e-6


def test_backtest_degrades_when_too_short():
    assert vol_managed_backtest(np.zeros(10))["available"] is False


@pytest.mark.skipif(not skfolio_available(), reason="skfolio non installé (adaptateur optionnel)")
def test_skfolio_weights_sum_to_one():
    rng = np.random.default_rng(1)
    mat = rng.normal(0.0005, 0.01, size=(120, 4))
    w = skfolio_weights(mat, "max_diversification")
    assert w is not None and abs(sum(w) - 1.0) < 1e-2


def test_skfolio_returns_none_without_lib_or_bad_input():
    # entrée invalide → None (le caller retombe sur nos optimiseurs numpy)
    assert skfolio_weights(np.zeros((2, 1))) is None
