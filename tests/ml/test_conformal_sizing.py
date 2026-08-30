import pytest

from packages.ml.sizing import conformal_weight


def test_conformal_sizing_ne_peut_pas_augmenter_la_cible():
    assert conformal_weight(0.2, 0.8, 0.3) == pytest.approx(0.16)


def test_conformal_sizing_force_zero_si_mandat_depasse():
    assert conformal_weight(0.2, 0.6, 0.3) == 0.0


def test_conformal_sizing_refuse_confiance_invalide():
    with pytest.raises(ValueError):
        conformal_weight(0.2, 1.1, 0.3)
