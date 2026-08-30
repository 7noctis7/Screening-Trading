import numpy as np
import pytest

from packages.research.kalman_causal import calibrate_train_only, causal_kalman


def _series():
    rng = np.random.default_rng(7)
    x = np.cumsum(rng.normal(size=120))
    y = 2.0 + 1.4 * x + rng.normal(scale=0.2, size=x.size)
    return y, x


def test_calibration_ne_voit_pas_le_futur():
    y, x = _series()
    first = calibrate_train_only(y, x, 80)
    y[80:], x[80:] = 1_000_000.0, -1_000_000.0
    assert calibrate_train_only(y, x, 80) == first


def test_prefixe_filtre_invariant_aux_observations_futures():
    y, x = _series()
    params = calibrate_train_only(y, x, 80)
    before = causal_kalman(y, x, params)["states"][:80]
    y[80:] *= -100
    after = causal_kalman(y, x, params)["states"][:80]
    np.testing.assert_allclose(before, after)


def test_calibration_refuse_un_train_trop_court():
    y, x = _series()
    with pytest.raises(ValueError, match="20"):
        calibrate_train_only(y, x, 10)
