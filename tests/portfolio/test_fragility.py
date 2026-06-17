import numpy as np
from packages.portfolio.fragility import fragility


def test_normal_is_robust():
    rng = np.random.default_rng(0)
    r = fragility(rng.normal(0, 0.01, 500))
    assert r["available"] and abs(r["excess_kurtosis"]) < 1.5


def test_fat_left_tail_is_fragile():
    rng = np.random.default_rng(1)
    r = np.concatenate([rng.normal(0.001, 0.005, 480), [-0.15, -0.2, -0.12, -0.18, -0.25]])
    f = fragility(r)
    assert f["available"] and (f["fragile"] or f["skew"] < 0)
