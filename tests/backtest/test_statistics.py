import numpy as np
from packages.backtest.statistics import (
    deflated_sharpe_ratio, expected_max_sharpe, probabilistic_sharpe_ratio,
)


def _rets(mean, std, n=500, seed=0):
    return np.random.default_rng(seed).normal(mean, std, n)


def test_psr_in_unit_interval():
    for seed in range(5):
        v = probabilistic_sharpe_ratio(_rets(0.001, 0.01, seed=seed))
        assert 0.0 <= v <= 1.0


def test_psr_high_for_strong_sharpe():
    strong = _rets(0.01, 0.01, n=500)   # SR ~ 1.0/période → très significatif
    assert probabilistic_sharpe_ratio(strong) > 0.95


def test_psr_around_half_for_zero_mean():
    flat = _rets(0.0, 0.01, n=1000, seed=3)
    flat = flat - flat.mean()           # SR exactement 0 → PSR(0) = Φ(0) = 0.5
    assert abs(probabilistic_sharpe_ratio(flat) - 0.5) < 1e-6


def test_expected_max_sharpe_increases_with_trials():
    a = expected_max_sharpe(5, 0.1)
    b = expected_max_sharpe(100, 0.1)
    assert b > a > 0


def test_dsr_penalises_many_trials():
    rets = _rets(0.0008, 0.01, n=500, seed=1)
    few = deflated_sharpe_ratio(rets, [0.05, 0.06, 0.04])          # peu d'essais
    many = deflated_sharpe_ratio(rets, list(np.linspace(0, 0.2, 200)))  # beaucoup
    assert many <= few
    assert 0.0 <= many <= 1.0
