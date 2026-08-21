"""Banc d'alpha : sans signal → ≈ 0 ; avec signal implanté → détecté. Et pas de fuite.

Panels SYNTHÉTIQUES : autorisé UNIQUEMENT pour valider la math et la PUISSANCE du banc
(CLAUDE.md). Aucun chiffre d'ici n'est une mesure d'alpha.
"""

import numpy as np
import pytest

from packages.research.alpha_hypotheses import (PRE_REGISTERED, SIGNALS,
                                                _residualize_oos,
                                                cross_sectional_backtest, h1_momentum,
                                                h4_reversal, h5_proximite_52w)


def _panel(seed=0, n=60, L=2200, momentum=0.0):
    """Panel à 3 facteurs. `momentum` > 0 implante une dérive idiosyncratique persistante."""
    rng = np.random.default_rng(seed)
    f = rng.normal(0, 0.01, (3, L))
    B = rng.normal(size=(n, 3))
    R = B @ f + rng.normal(0, 0.012, (n, L))
    if momentum > 0:
        R = R + rng.normal(0, momentum, (n, 1))
    return 100 * np.exp(np.cumsum(R, axis=1))


def test_toutes_les_hypotheses_sont_pre_enregistrees():
    assert set(SIGNALS) == set(PRE_REGISTERED)
    for params in PRE_REGISTERED.values():
        assert isinstance(params, dict) and params           # jamais de paramétrage vide


def test_signaux_elementaires_ont_le_bon_signe():
    A = np.array([[1.0, 2.0, 4.0], [4.0, 2.0, 1.0]])         # l'un monte, l'autre baisse
    rev = h4_reversal(A, 2, lookback=2)
    assert rev[0] < 0 < rev[1]                               # reversal : on vend le gagnant
    prox = h5_proximite_52w(A, 2, window=3)
    assert prox[0] == pytest.approx(1.0)                     # au plus haut
    assert prox[1] == pytest.approx(0.25)                    # loin du plus haut
    assert np.all(np.isnan(h1_momentum(A, 2, lookback=252, skip=21)))   # historique court


def test_residualisation_in_sample_absorbe_trop_de_variance():
    """LE piège corrigé : ajuster les facteurs sur la fenêtre où l'on MESURE retire de la
    variance qui n'est pas factorielle. Le résidu est trop petit, et son cumul devient
    anti-persistant par construction — le signal se retourne sans aucune information."""
    rng = np.random.default_rng(0)
    R = rng.normal(0, 0.01, (40, 400))            # AUCUNE structure factorielle réelle
    X = R[:, 200:] - R[:, 200:].mean(axis=1, keepdims=True)
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    in_sample = X - (U[:, :3] * S[:3]) @ Vt[:3]   # ajusté sur les données qu'il nettoie
    hors = _residualize_oos(R[:, :200], R[:, 200:], 3)   # loadings appris AVANT
    assert in_sample.std() < hors.std()           # l'in-sample absorbe du bruit pur
    assert hors.std() > 0.9 * X.std()             # le hors-échantillon préserve la variance
    assert hors.shape == X.shape


def test_sans_alpha_les_sharpes_restent_autour_de_zero():
    """3 tirages × 5 hypothèses : aucun Sharpe brut ne doit être systématiquement positif."""
    moyennes = {k: [] for k in SIGNALS}
    for seed in range(3):
        A = _panel(seed)
        for k in SIGNALS:
            r = cross_sectional_backtest(A, k, cost_rt_bps=0.0)
            assert r["available"]
            moyennes[k].append(r["sharpe"])
    for k, vals in moyennes.items():
        assert abs(float(np.mean(vals))) < 0.7, f"{k} systématiquement biaisé : {vals}"


def test_puissance_le_banc_detecte_un_momentum_implante():
    """Si le banc ne voit pas un effet PRÉSENT, ses négatifs ne valent rien."""
    sans = cross_sectional_backtest(_panel(9), "H1_momentum_12_1", cost_rt_bps=10.0)
    avec = cross_sectional_backtest(_panel(9, momentum=0.0006), "H1_momentum_12_1",
                                    cost_rt_bps=10.0)
    assert avec["sharpe"] > sans["sharpe"] + 0.2


def test_le_placebo_detruit_le_signal_pas_la_structure():
    A = _panel(9, momentum=0.0006)
    vrai = cross_sectional_backtest(A, "H1_momentum_12_1", cost_rt_bps=10.0)
    placebos = [cross_sectional_backtest(A, "H1_momentum_12_1", cost_rt_bps=10.0,
                                         shuffle_seed=s)["sharpe"] for s in range(12)]
    assert vrai["sharpe"] > float(np.mean(placebos))         # le classement porte l'effet
    assert abs(float(np.mean(placebos))) < 0.6               # permuté = plus d'information


def test_les_couts_degradent_toujours_le_resultat():
    A = _panel(2)
    brut = cross_sectional_backtest(A, "H4_reversal_5j", cost_rt_bps=0.0)
    net = cross_sectional_backtest(A, "H4_reversal_5j", cost_rt_bps=20.0)
    assert net["sharpe"] < brut["sharpe"]
    assert net["turnover_annual"] == brut["turnover_annual"]   # même trajectoire, autre coût


def test_long_only_et_garde_fous():
    A = _panel(3)
    lo = cross_sectional_backtest(A, "H1_momentum_12_1", long_only=True)
    assert lo["available"] and lo["long_only"] is True
    with pytest.raises(KeyError):
        cross_sectional_backtest(A, "H_inexistante")
    court = cross_sectional_backtest(_panel(0, L=300), "H1_momentum_12_1")
    assert court["available"] is False and court["status"] == "UNCALIBRATED"
