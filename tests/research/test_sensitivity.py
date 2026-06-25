"""Tests sensibilité (Jaccard sélection + dérive régime), hors-ligne."""

import numpy as np

from packages.research.sensitivity import (
    jaccard,
    regime_exposure_shift,
    selection_stability,
)


def test_jaccard_basics():
    assert jaccard([1, 2, 3], [1, 2, 3]) == 1.0
    assert jaccard([1, 2], [3, 4]) == 0.0
    assert jaccard([], []) == 1.0
    assert jaccard([1, 2, 3, 4], [1, 2]) == 0.5


def test_selection_stability_stable_vs_fragile():
    base = ["A", "B", "C", "D", "E"]
    stable = selection_stability(base, [["A", "B", "C", "D"], base])
    assert stable["stable"] is True and stable["jaccard_min"] >= 0.7
    fragile = selection_stability(base, [["A", "Z"], ["Y", "X"]])
    assert fragile["stable"] is False


def test_regime_exposure_shift_small_for_tiny_perturbation():
    rng = np.random.default_rng(0)
    mkt = 100 * np.cumprod(1 + rng.normal(0.0004, 0.01, 400))
    base = {"dd_hard": -0.15, "dd_soft": -0.10, "g_dist": 0.6, "g_below": 0.2}
    tiny = {**base, "g_dist": 0.61}
    out = regime_exposure_shift(mkt, base, tiny)
    assert out["available"] and out["mean_exposure_shift"] < 0.1 and out["stable"]
    # perturbation forte du frein → dérive mesurable
    big = {**base, "dd_hard": -0.05}
    out2 = regime_exposure_shift(mkt, base, big)
    assert out2["mean_exposure_shift"] >= out["mean_exposure_shift"]
