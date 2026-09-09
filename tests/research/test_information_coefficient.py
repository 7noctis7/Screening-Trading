"""Information Coefficient — la mesure qui manquait à `breadth.py`."""
import numpy as np

from packages.research.information_coefficient import (
    SEUIL_N_MIN,
    ic_in_sample_hors_echantillon,
    information_coefficient,
)


def test_correlation_parfaite_rend_ic_proche_de_un():
    rng = np.random.default_rng(0)
    predictions = rng.normal(size=30)
    rendements = predictions * 2.0 + 5.0            # relation MONOTONE parfaite
    ic = information_coefficient(predictions, rendements)
    assert ic is not None and ic > 0.99


def test_predictions_sans_rapport_au_hasard_rendent_ic_proche_de_zero():
    rng = np.random.default_rng(1)
    predictions = rng.normal(size=2000)
    rendements = rng.normal(size=2000)               # aucune relation, par construction
    ic = information_coefficient(predictions, rendements)
    assert ic is not None and abs(ic) < 0.05


def test_relation_inverse_rend_ic_negatif():
    predictions = np.array([5.0, 4.0, 3.0, 2.0, 1.0] * 5)
    rendements = np.array([1.0, 2.0, 3.0, 4.0, 5.0] * 5)
    ic = information_coefficient(predictions, rendements)
    assert ic is not None and ic < -0.99


def test_moins_de_20_paires_est_uncalibrated():
    """Sous le seuil, l'IC n'est pas fiable — None, jamais un chiffre optimiste."""
    p = list(range(SEUIL_N_MIN - 1))
    assert information_coefficient(p, p) is None


def test_variance_nulle_est_uncalibrated():
    """Un vecteur constant n'a pas de RANG à corréler — dégénéré, pas 0.0 mesuré."""
    p = [1.0] * 25
    r = np.random.default_rng(2).normal(size=25)
    assert information_coefficient(p, r) is None


def test_nan_sont_filtres_avant_le_seuil():
    rng = np.random.default_rng(3)
    p = rng.normal(size=30)
    r = p * 3.0
    p_troue = p.copy()
    p_troue[:15] = np.nan                             # ne laisse que 15 paires valides
    assert information_coefficient(p_troue, r) is None
    p_troue2 = p.copy()
    p_troue2[:5] = np.nan                              # 25 paires valides : mesurable
    assert information_coefficient(p_troue2, r) is not None


def test_tailles_differentes_leve_une_erreur():
    import pytest
    with pytest.raises(ValueError):
        information_coefficient([1.0, 2.0, 3.0], [1.0, 2.0])


def test_is_oos_ratio_et_robustesse():
    rng = np.random.default_rng(4)
    p_is = rng.normal(size=100)
    r_is = p_is * 2.0                                  # IC quasi 1 en IS
    p_oos = rng.normal(size=100)
    r_oos = rng.normal(size=100)                # IC quasi 0 en OOS : surapprentissage
    res = ic_in_sample_hors_echantillon(p_is, r_is, p_oos, r_oos)
    assert res.ic_in_sample is not None and res.ic_in_sample > 0.9
    assert res.ratio is not None and res.ratio < 0.5
    assert res.robuste is False


def test_is_oos_stable_est_robuste():
    rng = np.random.default_rng(5)
    p_is = rng.normal(size=100)
    r_is = p_is * 2.0 + rng.normal(scale=0.1, size=100)
    p_oos = rng.normal(size=100)
    r_oos = p_oos * 2.0 + rng.normal(scale=0.1, size=100)  # MÊME relation OOS
    res = ic_in_sample_hors_echantillon(p_is, r_is, p_oos, r_oos)
    assert res.robuste is True


def test_ratio_none_sans_mesure_des_deux_cotes():
    res = ic_in_sample_hors_echantillon([1.0] * 25, [2.0] * 25, [1, 2, 3], [1, 2, 3])
    assert res.ic_in_sample is None                     # variance nulle côté IS
    assert res.ratio is None and res.robuste is False    # jamais robuste par défaut
