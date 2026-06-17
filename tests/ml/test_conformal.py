import numpy as np
from packages.ml.conformal import calibrate_threshold, prediction_sets, evaluate


def test_coverage_close_to_target():
    rng = np.random.default_rng(0)
    n = 2000
    y = (rng.random(n) < 0.5).astype(float)
    p = np.clip(y * 0.7 + rng.random(n) * 0.3, 0, 1)      # signal informatif
    cut = n // 2
    res = evaluate(p[:cut], y[:cut], p[cut:], y[cut:], alpha=0.1)
    assert res["empirical_coverage"] >= 0.85               # ~90 % visé, tolérance
    assert 1.0 <= res["avg_set_size"] <= 2.0


def test_sets_never_empty():
    sets = prediction_sets([0.5, 0.99, 0.01], qhat=0.0)
    assert all(len(s) >= 1 for s in sets)


def test_threshold_in_unit_range():
    q = calibrate_threshold([0.2, 0.8, 0.6], [0, 1, 1], alpha=0.1)
    assert 0.0 <= q <= 1.0
