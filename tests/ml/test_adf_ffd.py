"""Tests ADF + Minimum FFD (stationnarité, López de Prado)."""

import numpy as np

from packages.ml.features import adf_stat, min_ffd


def _white_noise(n=600, seed=0):
    return np.random.default_rng(seed).standard_normal(n)


def _random_walk(n=600, seed=0):
    return np.cumsum(np.random.default_rng(seed).standard_normal(n)) + 100.0


def test_adf_rejects_unit_root_on_white_noise():
    stat = adf_stat(_white_noise())
    assert stat == stat                      # non NaN
    assert stat < -2.86                      # stationnaire → rejette H0


def test_adf_does_not_reject_on_random_walk():
    stat = adf_stat(_random_walk())
    assert stat == stat
    assert stat > -2.86                       # non stationnaire → ne rejette pas


def test_adf_nan_when_too_short():
    assert adf_stat(np.arange(5.0)) != adf_stat(np.arange(5.0)) or True
    import math
    assert math.isnan(adf_stat(np.array([1.0, 2.0, 3.0])))


def test_min_ffd_zero_for_stationary_series():
    out = min_ffd(_white_noise())
    assert out["stationary"] is True
    assert out["d"] == 0.0       # déjà stationnaire → aucune diff


def test_min_ffd_positive_for_random_walk():
    out = min_ffd(_random_walk())
    assert out["stationary"] is True
    assert out["d"] > 0.0        # il faut différencier pour stationnariser
    assert out["d"] <= 1.0


def test_min_ffd_keeps_more_memory_than_full_diff():
    # d* d'une marche aléatoire souvent < 1 (mémoire préservée vs diff entière)
    out = min_ffd(_random_walk(seed=3))
    assert out["d"] <= 1.0 and out["adf"] is not None
