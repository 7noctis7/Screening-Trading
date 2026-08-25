"""Alpha/bêta face au benchmark — ce qui distingue un signal d'un pari sur le marché."""

import numpy as np

from packages.research.alpha_hypotheses import benchmark_equipondere
from packages.research.attribution import attribution, bat_le_benchmark

PER_YEAR = 12.0


def test_strategie_qui_est_le_benchmark_na_pas_d_alpha():
    rng = np.random.default_rng(0)
    b = rng.normal(0.01, 0.04, 120)
    a = attribution(b, b, PER_YEAR)
    assert abs(a["beta"] - 1.0) < 1e-9
    assert abs(a["alpha_annuel"]) < 1e-9
    assert a["ir_exces"] == 0.0
    assert bat_le_benchmark(a) is False


def test_levier_pur_est_du_beta_pas_de_l_alpha():
    """1,5× le benchmark : Sharpe identique, bêta 1,5, alpha nul. Le gate doit le refuser."""
    rng = np.random.default_rng(1)
    b = rng.normal(0.01, 0.04, 200)
    a = attribution(1.5 * b, b, PER_YEAR)
    assert abs(a["beta"] - 1.5) < 1e-6
    assert abs(a["alpha_annuel"]) < 1e-6
    assert bat_le_benchmark(a) is False


def test_alpha_constant_est_detecte():
    rng = np.random.default_rng(2)
    b = rng.normal(0.008, 0.04, 200)
    a = attribution(b + 0.004, b, PER_YEAR)          # +0,4 %/mois d'excès pur
    assert abs(a["beta"] - 1.0) < 1e-6
    assert a["alpha_annuel"] > 0.04
    assert a["ir_exces"] > 5                          # excès sans volatilité → IR très élevé
    assert bat_le_benchmark(a) is True


def test_series_trop_courtes_ne_concluent_pas():
    a = attribution(np.zeros(4), np.zeros(4), PER_YEAR)
    assert a["available"] is False and bat_le_benchmark(a) is False


def test_benchmark_equipondere_tourne_sur_un_panel_synthetique():
    rng = np.random.default_rng(3)
    n, L = 40, 1400
    A = 100 * np.cumprod(1 + rng.normal(0.0004, 0.015, (n, L)), axis=1)
    b = benchmark_equipondere(A)
    assert b["available"] and b["n_steps"] > 8
    assert b["turnover_annual"] >= 0.0
    assert -1.0 < b["max_drawdown"] <= 0.0


def test_benchmark_refuse_un_historique_trop_court():
    A = np.ones((30, 100))
    assert benchmark_equipondere(A)["available"] is False
