"""Cap adaptatif corr-aware (rail prod) + plafond itéré partagé — math pure, offline."""

import numpy as np

from packages.backtest.preset_backtest import _adaptive_cap, _cap_weights


def _cov(n: int, rho: float, var: float = 0.04) -> np.ndarray:
    c = np.full((n, n), rho * var)
    np.fill_diagonal(c, var)
    return c


def test_cap_weights_plafonne_et_conserve_le_gross():
    w = np.array([0.5, 0.3, 0.1, 0.1])
    out = _cap_weights(w.copy(), 0.25)
    assert out.max() <= 0.25 + 1e-9
    assert abs(out.sum() - 1.0) < 1e-9                # gross conservé (renormalisé)


def test_cap_weights_noop_sous_le_plafond():
    w = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    assert np.allclose(_cap_weights(w.copy(), 0.25), w)


def test_adaptive_cap_resserre_en_stress_corr():
    calm = _adaptive_cap(_cov(10, 0.20), 0.10, corr_tighten=True)
    stress = _adaptive_cap(_cov(10, 0.80), 0.10, corr_tighten=True)
    assert calm == 0.10                               # diversification saine → cap inchangé
    assert stress == 0.05                             # breakdown → cap ÷2 (plus de noms imposés)


def test_adaptive_cap_off_par_flag():
    assert _adaptive_cap(_cov(10, 0.9), 0.10, corr_tighten=False) == 0.10
