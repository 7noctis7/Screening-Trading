"""Causalité alt-data : prouver l'avance prédictive, ou ne pas brancher la source."""
import numpy as np

from packages.research.causality import (betainc, f_pvalue, granger_both_ways,
                                         granger_causality, mi_permutation_test,
                                         mutual_information, pit_align, sidak_level)


def test_beta_incomplete_et_p_value_f_sur_valeurs_connues():
    assert abs(betainc(0.5, 0.5, 0.5) - 0.5) < 1e-9
    assert abs(betainc(2.0, 3.0, 0.5) - 0.6875) < 1e-9        # valeur exacte 11/16
    assert abs(f_pvalue(1.0, 10, 10) - 0.5) < 1e-9            # F(1) médian pour d1 = d2
    assert f_pvalue(5.0, 3, 100) < 0.01 and f_pvalue(0.1, 3, 100) > 0.9


def test_granger_detecte_une_avance_construite():
    rng = np.random.default_rng(0)
    n = 800
    x = rng.normal(size=n)
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.3 * y[t - 1] + 0.8 * x[t - 1] + 0.5 * rng.normal()
    r = granger_causality(y, x, lags=2, difference=False)
    assert r["causal"] is True and r["p_value"] < 1e-6 and r["r2_gain"] > 0.1


def test_series_independantes_ne_sont_pas_causales():
    rng = np.random.default_rng(1)
    faux = sum(granger_causality(rng.normal(size=500), rng.normal(size=500),
                                 lags=2, difference=False)["causal"] for _ in range(20))
    assert faux <= 3                                          # ~5 % de faux positifs attendus


def test_relation_bidirectionnelle_est_refusee_comme_predicteur():
    rng = np.random.default_rng(2)
    n = 600
    c = rng.normal(size=n)
    x = np.zeros(n)
    y = np.zeros(n)
    for t in range(1, n):                                     # boucle de rétroaction
        x[t] = 0.5 * y[t - 1] + c[t]
        y[t] = 0.5 * x[t - 1] + rng.normal()
    v = granger_both_ways(y, x, lags=2, difference=False)
    assert v["y_causes_x"]["causal"] is True
    assert v["usable_as_predictor"] is False and v["note"]


def test_granger_uncalibrated_sur_echantillon_court():
    r = granger_causality([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], lags=2)
    assert r["available"] is False and r["status"] == "UNCALIBRATED"


def test_information_mutuelle_capte_une_dependance_non_lineaire():
    rng = np.random.default_rng(3)
    x = rng.uniform(-2, 2, 2000)
    y_quad = x ** 2 + 0.3 * rng.normal(size=2000)             # corrélation linéaire ≈ 0
    assert abs(np.corrcoef(x, y_quad)[0, 1]) < 0.1
    assert granger_causality(y_quad, x, lags=1, difference=False)["p_value"] > 0.01
    assert mi_permutation_test(x, y_quad, bins=8, n_perm=100)["significant"] is True


def test_information_mutuelle_ne_signale_rien_sur_du_bruit():
    rng = np.random.default_rng(4)
    r = mi_permutation_test(rng.normal(size=1500), rng.normal(size=1500),
                            bins=8, n_perm=100)
    assert r["significant"] is False
    assert mutual_information(rng.normal(size=10), rng.normal(size=10))["available"] is False


def test_alignement_point_in_time_et_correction_multi_tests():
    from datetime import datetime
    dates = [datetime(2026, 1, 1), datetime(2026, 2, 1)]
    rows = pit_align(dates, [10.0, 12.0], publication_lag_days=21)
    assert rows[0]["realtime_start"] == datetime(2026, 1, 22)
    assert rows[0]["obs_date"] < rows[0]["realtime_start"]    # jamais connue le jour même
    assert sidak_level(0.05, 1) == 0.05 or abs(sidak_level(0.05, 1) - 0.05) < 1e-12
    assert sidak_level(0.05, 60) < 0.001                      # 12 sources × 5 horizons
