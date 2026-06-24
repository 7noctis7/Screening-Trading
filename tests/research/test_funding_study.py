"""Tests event-study funding (mean-reversion), déterministe hors-ligne."""

import numpy as np

from packages.research.funding_study import (
    aggregate_significance,
    fade_car,
    fade_events,
    significance,
    zscore_causal,
)


def test_zscore_causal_guards_and_positive():
    # passé plat (sd=0) → z=0 (garde-fou) ; pas d'historique → z=0
    z0 = zscore_causal([0.0] * 10 + [5.0], window=8)
    assert z0[0] == 0.0 and z0[10] == 0.0
    # passé varié + valeur haute → z élevé (et n'utilise QUE le passé)
    rng = np.random.default_rng(0)
    x = list(rng.normal(0, 1, 30)) + [10.0]
    z = zscore_causal(x, 30)
    assert z[-1] > 3


def test_fade_events_direction_is_opposite_sign():
    z = np.array([0.0, 2.0, -2.0, 0.5])
    ev = fade_events(z, threshold=1.5)
    assert ev == [(1, -1.0), (2, 1.0)]     # z>0 → short(-1), z<0 → long(+1)


def test_fade_car_signed():
    rets = np.array([0.0, 0.01, -0.02, 0.03, 0.0])
    # direction short (-1) sur (0, post] → −(0.01−0.02+0.03) = −0.02
    assert abs(fade_car(rets, 0, -1.0, post=3) - (-0.02)) < 1e-9


def _reverting(seed):
    rng = np.random.default_rng(seed)
    n = 400
    funding = rng.normal(0, 1e-5, n)        # bruit minuscule (sd>0)
    rets = rng.normal(0, 0.005, n)
    for e in (60, 120, 180, 240, 300, 360):
        funding[e] = 0.01                    # pic de funding positif → fade short
        rets[e + 1: e + 6] = -0.02           # reversion baissière → le short gagne
    return rets, zscore_causal(funding, 30)


def test_significance_detects_reversion():
    rets, z = _reverting(0)
    out = significance(rets, z, post=5, threshold=3.0, n_sims=300, seed=1)
    assert out["available"] and out["mean_car"] > 0 and out["significant"] is True


def test_random_not_significant():
    rng = np.random.default_rng(3)
    rets = rng.normal(0, 0.01, 400)
    z = zscore_causal(rng.normal(0, 0.001, 400), 30)
    out = significance(rets, z, post=5, threshold=1.5, n_sims=300, seed=2)
    assert (not out["available"]) or out["significant"] is False


def test_aggregate_pools_assets():
    r1, z1 = _reverting(0)
    r2, z2 = _reverting(5)
    out = aggregate_significance({"BTC": (r1, z1), "ETH": (r2, z2)},
                                 post=5, threshold=3.0, n_sims=300, seed=1)
    assert out["available"] and out["n_assets"] == 2 and out["significant"] is True
