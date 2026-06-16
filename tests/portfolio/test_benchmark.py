import numpy as np
from packages.portfolio import benchmark as B


def test_beta_and_capture_of_leveraged_clone():
    b = np.random.default_rng(0).normal(0.001, 0.01, 400)
    p = 1.5 * b                      # portefeuille = 1.5x le benchmark
    assert abs(B.beta(p, b) - 1.5) < 1e-6
    uc, dc = B.up_down_capture(p, b)
    assert abs(uc - 1.5) < 1e-6 and abs(dc - 1.5) < 1e-6


def test_information_ratio_zero_when_identical():
    b = np.random.default_rng(1).normal(0.001, 0.01, 200)
    assert B.information_ratio(b, b) == 0.0      # pas d'excès → TE=0 → IR=0


def test_r_squared_unit_for_linear():
    b = np.random.default_rng(2).normal(0, 0.01, 200)
    assert abs(B.r_squared(2 * b, b) - 1.0) < 1e-9
