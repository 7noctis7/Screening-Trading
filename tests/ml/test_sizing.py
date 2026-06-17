import numpy as np
from packages.ml.sizing import bet_size, evaluate_sizing


def test_bet_size_bounds_and_direction():
    s = bet_size([0.9, 0.1, 0.5], max_size=1.0)
    assert s[0] > 0 and s[1] < 0 and abs(s[2]) < 1e-9
    assert np.all(np.abs(s) <= 1.0)


def test_meta_confidence_scales_size():
    high = bet_size([0.9], [0.9])[0]
    low = bet_size([0.9], [0.2])[0]
    assert high > low                       # plus de confiance méta → mise plus grande


def test_evaluate_sizing_skillful_model_positive_pnl():
    rng = np.random.default_rng(0)
    y = (rng.random(500) < 0.5).astype(float)
    proba = np.clip(y * 0.7 + rng.random(500) * 0.3, 0, 1)   # informatif
    r = evaluate_sizing(proba, y)
    assert r["available"] and r["pnl_sized"] > 0
