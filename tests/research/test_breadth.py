"""Souffle effectif & loi fondamentale — le sur-comptage de BR est le piège testé ici."""
import numpy as np

from packages.research.breadth import (
    alpha_from_ic,
    autocorr,
    effective_breadth,
    effective_names,
    effective_periods,
    expected_ir,
    ic_at_horizon,
    ic_required,
    ir_report,
    mean_pairwise_corr,
    transfer_coefficient,
)


def test_signaux_independants_breadth_naif_egale_effectif():
    br = effective_breadth(50, 252, rho_cross=0.0, rho_time=0.0)
    assert br["breadth_eff"] == br["breadth_naive"] == 50 * 252
    assert br["overcount"] == 1.0


def test_signaux_correles_reduisent_le_souffle():
    assert effective_names(100, 0.5) < 3.0            # 100 noms corrélés à 0,5 ≈ 2 paris
    assert effective_periods(252, 0.9) < 20.0          # signal très lent ≈ 13 paris/an
    br = effective_breadth(100, 252, rho_cross=0.5, rho_time=0.9)
    assert br["overcount"] > 100                       # IR naïf surestimé d'un ordre 10×


def test_autocorr_et_corr_moyenne():
    lent = np.cumsum(np.random.default_rng(0).normal(size=500))
    assert autocorr(lent) > 0.9
    rng = np.random.default_rng(1)
    commun = rng.normal(size=300)
    panel = [commun + 0.3 * rng.normal(size=300) for _ in range(5)]
    assert mean_pairwise_corr(panel) > 0.7
    assert mean_pairwise_corr(rng.normal(size=(5, 300))) < 0.3


def test_transfer_coefficient_mesure_la_perte_des_contraintes():
    alphas = np.array([3.0, 2.0, 1.0, -1.0, -2.0, -3.0])
    assert transfer_coefficient(alphas, alphas) > 0.99          # non contraint
    long_only_cappe = np.clip(alphas, 0, 1.5)
    assert 0.0 < transfer_coefficient(alphas, long_only_cappe) < 0.99


def test_ir_ic_et_alpha_grinold():
    assert abs(expected_ir(0.05, 100.0, 1.0) - 0.5) < 1e-9
    assert abs(expected_ir(0.05, 100.0, 0.5) - 0.25) < 1e-9
    assert abs(ic_required(1.0, 100.0) - 0.1) < 1e-9
    a = alpha_from_ic([0.2, 0.4], 0.05, [1.0, -10.0])           # z écrêté à ±3
    assert abs(a[0] - 0.01) < 1e-12 and abs(a[1] + 0.06) < 1e-12


def test_ic_decroit_avec_l_horizon():
    assert abs(ic_at_horizon(0.06, half_life=5.0, horizon=5.0) - 0.03) < 1e-9
    assert ic_at_horizon(0.06, 5.0, 20.0) < 0.005


def test_rapport_uncalibrated_sans_mesure_reelle():
    r = ir_report(None, 50, 252)
    assert r["available"] is False and r["status"] == "UNCALIBRATED"
    ok = ir_report(0.04, 50, 252, rho_cross=0.4, rho_time=0.8, tc=0.5)
    assert ok["available"] and ok["overstatement_x"] > 5


def test_horizon_optimal_vaut_environ_1_8_demi_vie():
    from packages.research.breadth import optimal_horizon
    assert abs(optimal_horizon(10.0) / 10.0 - 1.81) < 0.01
    # vérification numérique directe de l'argmax de (1 − e^(−h/theta)) / √h
    theta = 10.0 / np.log(2.0)
    grid = np.linspace(0.1, 10 * theta, 20000)
    g = (1 - np.exp(-grid / theta)) / np.sqrt(grid)
    assert abs(grid[int(np.argmax(g))] - optimal_horizon(10.0)) < 0.05
    assert optimal_horizon(0.0) == 0.0
