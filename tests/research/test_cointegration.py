"""Cointégration : distinguer « bouge ensemble » (corrélation) de « revient » (stationnarité)."""
import numpy as np

from packages.research.cointegration import (
    adf_test,
    bonferroni_level,
    engle_granger,
    half_life,
    hedge_ratio,
    pair_verdict,
    spread_zscore,
)

# Séries SYNTHÉTIQUES : autorisé UNIQUEMENT en tests, pour valider la math (CLAUDE.md).
# Un générateur PAR TEST (seed explicite) → résultats indépendants de l'ordre d'exécution.


def _marche_aleatoire(seed, n=600, s=0.01):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(0, s, n)))


def _ou(seed, n=800, phi=0.9, s=1.0):
    rng = np.random.default_rng(seed)
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = phi * e[i - 1] + rng.normal(0, s)
    return e


def _paire_cointegree(seed, n=600, beta=1.5, kappa=0.05):
    """y = beta·x + bruit OU stationnaire → cointégrée par construction."""
    x = _marche_aleatoire(seed, n)
    return beta * x + _ou(seed + 1000, n, phi=1 - kappa), x


def test_adf_rejette_la_racine_unitaire_sur_serie_stationnaire():
    assert adf_test(_ou(1))["stationary"] is True
    assert adf_test(_marche_aleatoire(2, n=800))["stationary"] is False


def test_adf_valeurs_critiques_plus_strictes_pour_un_residu_estime():
    ou = _ou(3, n=500, phi=0.95)
    assert adf_test(ou, kind="eg2")["crit"] < adf_test(ou, kind="level")["crit"]


def test_adf_uncalibrated_si_echantillon_trop_court():
    r = adf_test([1.0, 2.0, 3.0])
    assert r["available"] is False and r["status"] == "UNCALIBRATED"


def test_hedge_ratio_retrouve_le_beta_et_le_spread():
    y, x = _paire_cointegree(4, beta=1.5)
    hr = hedge_ratio(y, x)
    assert abs(hr["beta"] - 1.5) < 0.15
    assert abs(float(np.mean(hr["spread"]))) < 1.0


def test_demi_vie_ou_positive_et_divergence_detectee():
    hl = half_life(_ou(5, n=1000))
    assert hl["mean_reverting"] and 3.0 < hl["half_life"] < 12.0     # ln2/0,105 ≈ 6,6
    lente = half_life(_marche_aleatoire(6, n=800))                   # marche aléatoire :
    assert lente["half_life"] is None or lente["half_life"] > 30.0   # pas de rappel utile


def test_paire_cointegree_detectee_marche_aleatoire_rejete():
    y, x = _paire_cointegree(7)
    assert engle_granger(y, x)["cointegrated"] is True
    assert engle_granger(_marche_aleatoire(8),
                         _marche_aleatoire(9))["cointegrated"] is False


def test_correlation_forte_sans_cointegration_est_rejetee():
    """Deux marches aléatoires à choc commun : corrélation ≈ 0,9, spread NON stationnaire."""
    rng = np.random.default_rng(11)
    commun = rng.normal(0, 0.012, 800)
    a = 100 * np.exp(np.cumsum(commun + rng.normal(0, 0.005, 800)))
    b = 100 * np.exp(np.cumsum(commun + rng.normal(0, 0.005, 800)))
    corr = np.corrcoef(np.diff(np.log(a)), np.diff(np.log(b)))[0, 1]
    assert corr > 0.7                                   # « très corrélées »…
    assert engle_granger(a, b)["cointegrated"] is False  # …et pourtant intradables


def test_multiple_testing_durcit_le_seuil():
    assert abs(bonferroni_level(0.05, 1) - 0.05) < 1e-12
    assert bonferroni_level(0.05, 4950) < 1e-4          # 100 actifs = 4950 paires


def test_verdict_exige_les_deux_sens_et_une_demi_vie_exploitable():
    y, x = _paire_cointegree(12)
    v = pair_verdict(y, x, hl_min=1.0, hl_max=60.0)
    assert v["tradable"] is True and v["reasons"] == []
    trop_lent = pair_verdict(y, x, hl_min=1.0, hl_max=2.0)
    assert trop_lent["tradable"] is False and "demi-vie" in trop_lent["reasons"][0]
    assert pair_verdict(_marche_aleatoire(13),
                        _marche_aleatoire(14))["tradable"] is False


def test_zscore_glissant_sur_fenetre_recente():
    s = np.concatenate([np.zeros(200), [3.0]])
    assert spread_zscore(s, lookback=60) > 5.0
    assert spread_zscore([1.0] * 5) is None
