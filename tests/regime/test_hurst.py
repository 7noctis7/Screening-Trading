"""Hurst R/S : le biais de petit échantillon est le piège n° 1, on le fige en test.

Séries SYNTHÉTIQUES : autorisé UNIQUEMENT pour valider la math (CLAUDE.md).
"""

import numpy as np

from packages.regime.hurst import (_expected_rs, hurst_rs, hurst_significance,
                                   regime_from_hurst, rolling_hurst)


def _ar1(phi, n=4000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal()
    return x


def test_rs_brut_est_biaise_vers_le_haut_sur_du_bruit_pur():
    """LE piège : sans correction, une marche aléatoire sort « tendance »."""
    bruit = np.random.default_rng(0).normal(size=4000)
    brut = hurst_rs(bruit, corrected=False)["hurst"]
    corrige = hurst_rs(bruit)["hurst"]
    assert brut > 0.55                                # conclusion fausse « persistant »
    assert abs(corrige - 0.5) < 0.03                  # la correction ramène à 0,5
    assert corrige < brut


def test_esperance_anis_lloyd_croit_en_racine_de_n():
    """E[R/S] ≈ sqrt(n·pi/2) asymptotiquement : le ratio doit tendre vers 1."""
    for n in (400, 800, 1600):
        assert abs(_expected_rs(n) / np.sqrt(n * np.pi / 2) - 1.0) < 0.05
    assert _expected_rs(50) < _expected_rs(200) < _expected_rs(800)


def test_persistance_et_anti_persistance_sont_distinguees():
    h_pos = hurst_rs(_ar1(0.45, seed=1))["hurst"]
    h_neg = hurst_rs(_ar1(-0.45, seed=1))["hurst"]
    assert h_pos > 0.55                               # mémoire positive → tendance
    assert h_neg < 0.47                               # mémoire négative → retour à la moyenne
    assert h_pos > h_neg + 0.1


def test_qualite_de_l_ajustement_log_log_est_publiee():
    r = hurst_rs(_ar1(0.3, seed=2))
    assert r["r2"] > 0.9                              # la loi de puissance tient
    assert r["n_windows"] >= 4 and r["window_min"] >= 10


def test_bande_nulle_par_permutation():
    """La permutation détruit la mémoire : le bruit doit rester DANS la bande, l'AR non."""
    bruit = np.random.default_rng(3).normal(size=3000)
    assert hurst_significance(bruit, n_perm=80, seed=1)["significant"] is False
    fort = hurst_significance(_ar1(0.6, n=3000, seed=3), n_perm=80, seed=1)
    assert fort["significant"] is True and fort["hurst"] > fort["null_hi"]


def test_verdict_operationnel_coupe_l_allocation_sur_du_bruit():
    bruit = np.random.default_rng(4).normal(size=3000)
    v = regime_from_hurst(bruit, n_perm=60)
    assert v["regime"] == "marche_aleatoire" and "aucune allocation" in v["action"]

    tendance = regime_from_hurst(_ar1(0.6, n=3000, seed=4), n_perm=60)
    assert tendance["regime"] == "persistant" and "momentum" in tendance["action"]

    reversion = regime_from_hurst(_ar1(-0.6, n=3000, seed=4), n_perm=60)
    assert reversion["regime"] == "anti_persistant"
    assert "arbitrage statistique" in reversion["action"]


def test_uncalibrated_sous_le_minimum_et_fenetre_glissante_causale():
    assert hurst_rs(np.zeros(20))["status"] == "UNCALIBRATED"
    assert rolling_hurst(np.zeros(50), window=252)["status"] == "UNCALIBRATED"
    roll = rolling_hurst(_ar1(0.4, n=2000, seed=5), window=500, step=100)
    assert roll["available"] and len(roll["hurst"]) == len(roll["index"])
    assert roll["index"][0] == 499                    # 1re valeur = fin de la 1re fenêtre
    assert roll["last"] == roll["hurst"][-1]
