"""Tests overlay de risque (taper drawdown × cible vol forward-aware), hors-ligne."""

import numpy as np

from packages.portfolio.risk_overlay import (
    drawdown_taper,
    recommended_exposure,
    vol_target_fraction,
)


def test_drawdown_taper_boundaries_and_linearity():
    assert drawdown_taper(0.0) == 1.0           # pas de drawdown → plein
    assert drawdown_taper(-0.05) == 1.0         # au-dessus du soft
    assert drawdown_taper(-0.25) == 0.0         # sous le hard → coupe
    assert drawdown_taper(-0.15, -0.10, -0.20) == 0.5   # milieu → 50 %


def test_vol_target_fraction_caps_and_scales():
    # vol élevée → fraction faible
    assert vol_target_fraction(0.10, realized=0.40) == 0.25
    # vol faible → plafonné à max_frac (pas d'explosion)
    assert vol_target_fraction(0.10, realized=0.01, max_frac=1.0) == 1.0
    # la vol PRÉVUE (forecast) prend le dessus si plus haute
    assert vol_target_fraction(0.10, realized=0.10, forecast=0.50) == 0.20


def test_recommended_exposure_calm_full_vs_crisis_zero():
    rng = np.random.default_rng(0)
    calm = rng.normal(0.0005, 0.005, 300)        # tendance douce, faible vol → plein
    out = recommended_exposure(calm, target_vol=0.10)
    assert out["available"] and out["exposure"] > 0.5

    crash = np.concatenate([rng.normal(0.0005, 0.005, 200),
                            np.full(40, -0.03)])  # gros drawdown récent → coupe
    oc = recommended_exposure(crash, target_vol=0.10)
    assert oc["drawdown"] < -0.10 and oc["exposure"] < out["exposure"]


def test_recommended_exposure_short_series_guard():
    assert recommended_exposure([0.01, 0.02])["available"] is False
