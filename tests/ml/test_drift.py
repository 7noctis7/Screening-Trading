import numpy as np
from packages.ml import psi, drift_status, feature_drift


def test_psi_zero_for_same_distribution():
    rng = np.random.default_rng(0)
    assert psi(rng.normal(0, 1, 2000), rng.normal(0, 1, 2000)) < 0.1


def test_psi_high_for_shifted():
    rng = np.random.default_rng(0)
    p = psi(rng.normal(0, 1, 2000), rng.normal(3, 1, 2000))
    assert p > 0.25 and drift_status(p) == "fort"


def test_feature_drift_flags():
    rng = np.random.default_rng(1)
    ref = rng.normal(0, 1, (500, 2))
    cur = np.column_stack([rng.normal(0, 1, 500), rng.normal(4, 1, 500)])  # 2e dérive
    out = feature_drift(ref, cur, ["f0", "f1"])
    assert out["drift_detected"] and "f1" in out["flagged"]
