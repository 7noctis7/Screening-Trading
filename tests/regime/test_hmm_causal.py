"""HMM causal : la sentinelle de non-fuite est LE test de ce module.

Séries SYNTHÉTIQUES : autorisé UNIQUEMENT pour valider la math (CLAUDE.md).
"""

import numpy as np

from packages.regime.hmm_causal import (baum_welch, causal_regime_path,
                                        filtered_probabilities, hysteresis, viterbi)


def _deux_regimes(T=1500, p_reste=0.97, seed=0):
    """Calme (sd 0,5) / stress (sd 2,5), tous deux persistants."""
    rng = np.random.default_rng(seed)
    s = np.zeros(T, dtype=int)
    for t in range(1, T):
        s[t] = s[t - 1] if rng.random() < p_reste else 1 - s[t - 1]
    x = np.where(s == 0, rng.normal(0.02, 0.5, T), rng.normal(-0.05, 2.5, T))
    return x, s


def test_baum_welch_retrouve_les_parametres():
    x, _ = _deux_regimes()
    f = baum_welch(x, k=2)
    assert f["available"]
    assert abs(f["sd"][0] - 0.5) < 0.15 and abs(f["sd"][1] - 2.5) < 0.3
    assert np.all(np.diag(f["A"]) > 0.9)              # les deux régimes sont persistants
    assert np.allclose(f["A"].sum(axis=1), 1.0)       # matrice stochastique


def test_etiquetage_stable_les_etats_sont_ordonnes_par_volatilite():
    """Sans cet ordre, l'EM permute les labels et « stress » devient « calme » en silence."""
    x, _ = _deux_regimes(seed=1)
    for seed in (0, 1, 2, 3):
        f = baum_welch(x, k=2, seed=seed)
        assert f["sd"][0] < f["sd"][1]                # état 0 = calme, dernier = stress
    f3 = baum_welch(x, k=3, seed=0)
    assert list(f3["sd"]) == sorted(f3["sd"])


def test_probabilites_filtrees_sont_des_probabilites():
    x, _ = _deux_regimes(seed=2)
    a = filtered_probabilities(x, baum_welch(x, k=2))
    assert a.shape == (x.size, 2)
    assert np.allclose(a.sum(axis=1), 1.0) and np.all(a >= 0)


def test_le_chemin_causal_ne_depend_PAS_du_futur():
    """SENTINELLE : tronquer la série à t doit donner EXACTEMENT le même chemin sur [0, t]."""
    x, _ = _deux_regimes(T=1500, seed=3)
    complet = causal_regime_path(x, min_train=400, refit_every=100)
    tronque = causal_regime_path(x[:1200], min_train=400, refit_every=100)
    assert np.array_equal(complet["states"][:1200], tronque["states"][:1200])
    p_a, p_b = complet["p_stress"][:1200], tronque["p_stress"][:1200]
    fini = np.isfinite(p_a)
    assert np.allclose(p_a[fini], p_b[fini])


def test_le_lissage_voit_le_futur_et_bat_le_filtre():
    """L'écart Viterbi/filtré CHIFFRE ce que coûte l'honnêteté — et prouve la fuite évitée."""
    x, s = _deux_regimes(T=1500, seed=4)
    lisse = viterbi(x, baum_welch(x, k=2))
    causal = causal_regime_path(x, min_train=400, refit_every=100)
    vus = causal["states"] >= 0
    acc_lisse = float((lisse[vus] == s[vus]).mean())
    acc_causal = float((causal["states"][vus] == s[vus]).mean())
    assert acc_causal > 0.85                          # le filtre reste très bon…
    assert acc_lisse > acc_causal                     # …mais le lissage triche, et ça se voit


def test_hysteresis_reduit_les_allers_retours():
    p = np.array([0.1] * 20 + [0.5, 0.8, 0.5, 0.8, 0.5, 0.8] + [0.1] * 20)
    seuil_unique = (p > 0.5).astype(int)
    avec = hysteresis(p, enter=0.70, exit_=0.40)
    assert np.abs(np.diff(avec)).sum() < np.abs(np.diff(seuil_unique)).sum()
    assert avec[0] == 0 and avec[21] == 1             # entre à 0,8 …
    assert avec[22] == 1                              # … et ne sort pas à 0,5 (> exit_)


def test_uncalibrated_sur_echantillon_court():
    assert baum_welch(np.zeros(10), k=2)["status"] == "UNCALIBRATED"
    assert causal_regime_path(np.zeros(100), min_train=250)["status"] == "UNCALIBRATED"
