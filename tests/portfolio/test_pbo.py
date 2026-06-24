"""Tests PBO/CSCV (hors-ligne, déterministe)."""

import numpy as np

from packages.portfolio.pbo import pbo_cscv


def test_pbo_low_for_genuinely_best_config():
    # config 0 a une vraie dérive positive constante ; les autres = bruit pur centré.
    rng = np.random.default_rng(0)
    t, n = 400, 5
    mat = rng.normal(0, 0.01, size=(t, n))
    mat[:, 0] += 0.004                       # edge réel et stable → robuste OOS
    out = pbo_cscv(mat, n_splits=10)
    assert out["available"] and out["pbo"] < 0.3   # championne IS reste bonne OOS


def test_pbo_high_for_pure_noise():
    # que du bruit : la « meilleure » IS est aléatoire → s'effondre OOS → PBO ≈ 0.5+
    rng = np.random.default_rng(1)
    mat = rng.normal(0, 0.01, size=(400, 8))
    out = pbo_cscv(mat, n_splits=10)
    assert out["available"] and out["pbo"] > 0.35


def test_pbo_guards():
    assert pbo_cscv(np.zeros((100, 1)))["available"] is False     # <2 configs
    assert pbo_cscv(np.zeros((4, 3)), n_splits=10)["available"] is False  # T<S
