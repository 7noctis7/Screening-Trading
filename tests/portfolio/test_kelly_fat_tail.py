"""Kelly à queues épaisses : la mise doit tomber quand la queue gauche s'épaissit."""
import numpy as np

from packages.portfolio.sizing.kelly_fat_tail import (drawdown_probability, growth_rate,
                                                      kelly_empirical,
                                                      lambda_from_drawdown, ruin_bound,
                                                      sized_fraction)


def test_kelly_empirique_retrouve_le_cas_binomial_connu():
    """Pile ou face à 60 %, gain = perte : Kelly = 2p − 1 = 0,20."""
    r = [0.5] * 600 + [-0.5] * 400              # p = 0,6, payoff 1:1 → f* = 0,2 / 0,5
    assert abs(kelly_empirical(r) - 0.4) < 0.01  # f en fraction du capital : 2p−1 = 0,2 → /0,5


def test_kelly_nul_si_esperance_negative():
    assert kelly_empirical([0.1] * 40 + [-0.1] * 60) == 0.0
    assert kelly_empirical([-0.01] * 100) == 0.0


def test_borne_de_ruine_est_respectee():
    r = [0.05] * 90 + [-0.20] * 10
    assert ruin_bound(r) == 5.0
    assert kelly_empirical(r) < 5.0
    assert growth_rate(5.0, r) == float("-inf")   # f = 1/|perte| ⇒ capital nul


def test_queue_gpd_ajoutee_reduit_la_mise():
    rng = np.random.default_rng(3)
    base = list(rng.normal(0.004, 0.02, 400))
    sans = sized_fraction(base, cap=1.0)
    avec = sized_fraction(base, cap=1.0, tail_losses=[-0.25, -0.35, -0.50])
    assert avec["fraction"] < sans["fraction"]


def test_lambda_derive_du_budget_de_drawdown():
    assert abs(lambda_from_drawdown(0.50, 0.01) - 0.262) < 0.005   # quart de Kelly, dérivé
    assert abs(lambda_from_drawdown(0.25, 0.05) - 0.175) < 0.005   # DD 25 % → ~1/6 de Kelly
    assert lambda_from_drawdown(0.25, 0.01) < lambda_from_drawdown(0.25, 0.05)
    assert lambda_from_drawdown(0.0, 0.05) == 0.0


def test_reciprocite_lambda_probabilite_de_drawdown():
    for dd, eps in [(0.5, 0.01), (0.25, 0.05), (0.15, 0.10)]:
        assert abs(drawdown_probability(lambda_from_drawdown(dd, eps), dd) - eps) < 1e-6
    assert abs(drawdown_probability(1.0, 0.5) - 0.5) < 1e-9        # Kelly complet : 50 %


def test_uncalibrated_sous_le_minimum_de_trades():
    r = sized_fraction([0.01] * 10)
    assert r["available"] is False and r["status"] == "UNCALIBRATED" and r["n"] == 10
