"""Combinaison de signaux : la décorrélation crée la valeur, et la pondération ne triche pas.

Panels SYNTHÉTIQUES : valider la math et la puissance du banc, jamais mesurer de l'alpha.
"""

import numpy as np
import pytest

from packages.research.alpha_combine import (breadth_report, combined_backtest,
                                             measure_ics, rank_ic, signal_correlation)
from packages.research.alpha_hypotheses import SIGNALS

NAMES = list(SIGNALS)


def _panel(seed=0, n=120, L=2600, momentum=0.0):
    rng = np.random.default_rng(seed)
    f = rng.normal(0, 0.01, (3, L))
    B = rng.normal(size=(n, 3))
    R = B @ f + rng.normal(0, 0.012, (n, L))
    if momentum > 0:
        R = R + rng.normal(0, momentum, (n, 1))
    return 100 * np.exp(np.cumsum(R, axis=1))


def test_rank_ic_est_une_correlation_de_rang():
    x = np.arange(50, dtype=float)
    assert rank_ic(x, x) == pytest.approx(1.0)
    assert rank_ic(x, -x) == pytest.approx(-1.0)
    assert rank_ic(x, np.r_[x[:25], x[:25]]) is not None
    assert rank_ic(np.array([1.0, 2.0]), np.array([1.0, 2.0])) is None    # trop court
    bruite = np.random.default_rng(0).normal(size=200)
    assert abs(rank_ic(bruite, np.random.default_rng(1).normal(size=200))) < 0.25


def test_ic_mesure_est_nul_sans_signal_et_positif_avec():
    sans = measure_ics(_panel(1), ["H1_momentum_12_1"])
    avec = measure_ics(_panel(1, momentum=0.0008), ["H1_momentum_12_1"])
    assert sans["available"] and avec["available"]
    ic_sans = sans["par_signal"]["H1_momentum_12_1"]["ic_mean"]
    ic_avec = avec["par_signal"]["H1_momentum_12_1"]["ic_mean"]
    assert abs(ic_sans) < 0.05
    assert ic_avec > ic_sans + 0.02                    # le momentum implanté se voit


def test_la_matrice_de_correlation_des_signaux_est_valide():
    O = signal_correlation(_panel(2), NAMES)
    assert O.shape == (len(NAMES), len(NAMES))
    assert np.allclose(np.diag(O), 1.0, atol=1e-6)
    assert np.allclose(O, O.T, atol=1e-9)
    assert np.abs(O[~np.eye(len(NAMES), dtype=bool)]).max() <= 1.0


def test_la_combinaison_bat_le_meilleur_signal_seul_en_IC():
    """C'est LA raison d'être de la combinaison : IC_combiné = √(ic'·Ω⁻¹·ic) ≥ max|ic|."""
    A = _panel(3, momentum=0.0006)
    br = breadth_report(A, NAMES, measure_ics(A, NAMES))
    assert br["ic_combine"] >= br["ic_meilleur_seul"] - 1e-9
    assert br["n_noms"] == 120 and br["n_signaux"] == len(NAMES)
    assert br["ir_theorique_TC1"] > br["ir_realiste_TC05"]      # le transfert coûte
    assert br["ic_requis_pour_IR1"] > 0


def test_la_ponderation_n_utilise_que_le_passe():
    """SENTINELLE : tronquer l'historique ne doit pas changer le début de la courbe."""
    A = _panel(4, momentum=0.0006)
    complet = combined_backtest(A, NAMES, cost_rt_bps=10.0)
    tronque = combined_backtest(A[:, :2200], NAMES, cost_rt_bps=10.0)
    assert complet["available"] and tronque["available"]
    k = min(complet["returns"].size, tronque["returns"].size)
    assert k >= 8
    # On exclut le DERNIER pas de la série tronquée : sa fenêtre de détention est écrêtée
    # par la fin du tableau (effet de bord d'échantillon, pas une fuite d'information).
    assert np.allclose(complet["returns"][:k - 1], tronque["returns"][:k - 1], atol=1e-12)
    assert not np.allclose(complet["returns"][:k], tronque["returns"][:k], atol=1e-12)


def test_les_poids_de_signaux_sont_une_repartition_sans_inversion():
    c = combined_backtest(_panel(5, momentum=0.0006), NAMES, cost_rt_bps=10.0)
    poids = np.array(list(c["poids_finaux"].values()))
    assert np.all(poids >= 0.0)                        # jamais d'inversion a posteriori
    assert abs(poids.sum() - 1.0) < 1e-6


def test_le_livre_combine_profite_du_signal_implante():
    sans = combined_backtest(_panel(6), NAMES, cost_rt_bps=10.0)
    avec = combined_backtest(_panel(6, momentum=0.0008), NAMES, cost_rt_bps=10.0)
    assert avec["sharpe"] > sans["sharpe"] + 0.3


def test_uncalibrated_sur_historique_court():
    court = combined_backtest(_panel(0, L=700), NAMES)
    assert court["available"] is False and court["status"] == "UNCALIBRATED"
    assert measure_ics(_panel(0, L=600), NAMES, start=520)["available"] is False
