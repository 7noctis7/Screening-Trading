"""Almgren-Chriss : la forme de la trajectoire encode l'arbitrage coût / risque."""
import math

from packages.execution.almgren_chriss import (cap_by_participation, efficient_frontier,
                                               kappa_from_risk, trajectory)

BASE = dict(x_total=100_000.0, horizon=1.0, n_steps=20, sigma=0.3, eta=2.5e-6, gamma=2.5e-7)


def test_neutre_au_risque_redonne_exactement_le_twap():
    r = trajectory(**BASE, lam=0.0)
    assert r["is_twap"] and abs(r["front_loading"] - 1.0) < 1e-9
    attendu = [100_000.0 * (1 - j / 20) for j in range(21)]
    assert max(abs(a - b) for a, b in zip(r["holdings"], attendu)) < 1e-6


def test_aversion_au_risque_accelere_l_execution():
    lent = trajectory(**BASE, lam=1e-7)
    vite = trajectory(**BASE, lam=1e-5)
    assert vite["kappa"] > lent["kappa"] > 0
    assert vite["front_loading"] > lent["front_loading"] > 1.0
    assert vite["half_life"] < lent["half_life"]
    for a, b in zip(vite["holdings"][1:-1], lent["holdings"][1:-1]):
        assert a < b                                  # toujours moins de risque résiduel


def test_arbitrage_cout_contre_variance():
    frontiere = efficient_frontier(**BASE, lams=[0.0, 1e-7, 1e-6, 1e-5])
    couts = [p["expected_cost"] for p in frontiere]
    ecarts = [p["stdev"] for p in frontiere]
    assert couts == sorted(couts)                     # payer plus…
    assert ecarts == sorted(ecarts, reverse=True)     # …pour risquer moins


def test_conservation_de_la_quantite_et_liquidation_complete():
    for lam in (0.0, 1e-6, 1e-4):
        r = trajectory(**BASE, lam=lam)
        assert abs(sum(r["trades"]) - 100_000.0) < 1e-6
        assert r["holdings"][-1] == 0.0
        assert all(t > 0 for t in r["trades"])        # jamais de rachat en cours de vente


def test_le_temps_caracteristique_ne_depend_pas_de_la_taille():
    petit = trajectory(**{**BASE, "x_total": 1_000.0}, lam=1e-6)
    gros = trajectory(**{**BASE, "x_total": 5_000_000.0}, lam=1e-6)
    assert abs(petit["half_life"] - gros["half_life"]) < 1e-9
    assert gros["expected_cost"] > petit["expected_cost"]


def test_kappa_resout_bien_l_equation_de_cosh():
    tau = 1.0 / 20
    k = kappa_from_risk(lam=1e-6, sigma=0.3, eta=2.5e-6, gamma=2.5e-7, tau=tau)
    assert abs(math.cosh(k["kappa"] * tau) - (1 + k["kappa_tilde2"] * tau**2 / 2)) < 1e-9


def test_intervalles_trop_longs_sont_refuses_et_pas_bricoles():
    ko = trajectory(x_total=1000, horizon=1.0, n_steps=1, sigma=0.3,
                    eta=1e-8, gamma=1e-3, lam=1e-6)
    assert ko["available"] is False and "eta_tilde" in ko["reason"]


def test_plafond_de_participation_declare_l_horizon_infaisable():
    r = trajectory(**BASE, lam=1e-4)
    serre = cap_by_participation(r["trades"], bar_volume=20_000, pov=0.10)
    assert serre["feasible"] is False and serre["n_binding"] > 0
    large = cap_by_participation(r["trades"], bar_volume=10_000_000, pov=0.10)
    assert large["feasible"] is True and large["n_binding"] == 0
