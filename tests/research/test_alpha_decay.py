"""Tests alpha decay + impact Almgren — purs, hors-ligne."""

import math

import numpy as np

from packages.research.alpha_decay import (
    almgren_impact,
    apply_impact,
    ic_half_life,
    rolling_ic,
)


def test_ic_half_life_exponential():
    # IC qui décroît avec demi-vie connue (3) → λ = ln2/3
    lam = math.log(2) / 3
    ics = [0.4 * math.exp(-lam * h) for h in range(8)]
    out = ic_half_life(ics)
    assert out["available"] and abs(out["half_life"] - 3) < 0.3


def test_ic_half_life_flat_no_decay():
    out = ic_half_life([0.3, 0.3, 0.3, 0.3])
    assert out["available"] and out["decays"] is False


def test_almgren_sqrt_law():
    # 4× la taille → ~2× l'impact (racine carrée)
    i1 = almgren_impact(qty=1, adv=100, sigma=0.02)
    i4 = almgren_impact(qty=4, adv=100, sigma=0.02)
    assert abs(i4 / i1 - 2.0) < 1e-6
    assert almgren_impact(0, 100, 0.02) == 0.0 and almgren_impact(1, 0, 0.02) == 0.0


def test_apply_impact_reduces_returns():
    g = [0.01, 0.01, 0.01]
    net = apply_impact(g, turnover_per_period=0.5, adv_ratio=0.04, sigma=0.03)
    assert (net < np.asarray(g)).all()


def test_rolling_ic_detects_relation():
    rng = np.random.default_rng(0)
    sig = rng.normal(0, 1, 200)
    fwd = sig * 0.5 + rng.normal(0, 0.5, 200)        # corrélé positivement
    ics = rolling_ic(sig, fwd, window=60)
    assert len(ics) > 0 and np.mean(ics) > 0.2
