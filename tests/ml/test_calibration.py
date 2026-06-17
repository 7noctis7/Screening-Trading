import numpy as np
from packages.ml.calibration import brier_score, reliability_curve, PlattCalibrator


def test_brier_perfect_vs_random():
    y = [1, 0, 1, 0]
    assert brier_score(y, [1, 0, 1, 0]) == 0.0
    assert brier_score(y, [0.5] * 4) == 0.25


def test_platt_improves_or_keeps_brier():
    rng = np.random.default_rng(0)
    y = (rng.random(400) < 0.5).astype(float)
    scores = y * 0.6 + rng.random(400) * 0.4          # signal + bruit, mal calibré
    cal = PlattCalibrator().fit(scores, y)
    p = cal.transform(scores)
    assert 0.0 <= p.min() and p.max() <= 1.0
    assert brier_score(y, p) <= brier_score(y, scores) + 0.05


def test_reliability_curve_bins():
    y = [1, 0, 1, 1, 0]
    rc = reliability_curve(y, [0.9, 0.1, 0.8, 0.7, 0.2], bins=5)
    assert all(0 <= b["pred"] <= 1 and 0 <= b["obs"] <= 1 for b in rc)
