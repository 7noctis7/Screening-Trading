"""Sharpe probabiliste (PSR) & déflaté (DSR) — Bailey & López de Prado.

Corrige le Sharpe pour : taille d'échantillon, non-normalité (skew/kurtosis) ET
**multiple testing** (combien de configurations on a essayées). Un Sharpe élevé
obtenu après N essais n'est pas significatif s'il ne bat pas le seuil déflaté.

Stdlib only (`statistics.NormalDist` pour Φ et Φ⁻¹). Le Sharpe ici est PAR PÉRIODE
(non annualisé) : SR = mean(returns)/std(returns).
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np

_NORM = NormalDist()
_EULER = 0.5772156649015329  # constante d'Euler-Mascheroni


def _moments(returns: np.ndarray) -> tuple[float, float, float, int]:
    """SR par période, skew, kurtosis (Fisher, normale=3 ici en 'non-excess'), n."""
    n = returns.size
    mu, sd = returns.mean(), returns.std(ddof=1)
    sr = mu / sd if sd > 0 else 0.0
    z = (returns - mu) / sd if sd > 0 else np.zeros_like(returns)
    skew = float((z**3).mean())
    kurt = float((z**4).mean())  # kurtosis non-excess (3 = normale)
    return sr, skew, kurt, n


def probabilistic_sharpe_ratio(returns: np.ndarray, benchmark_sr: float = 0.0) -> float:
    """PSR(benchmark_sr) = P(SR_vrai > benchmark_sr). Dans [0, 1]."""
    sr, skew, kurt, n = _moments(np.asarray(returns, float))
    if n < 3:
        return 0.0
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr**2))
    stat = (sr - benchmark_sr) * math.sqrt(n - 1) / denom
    return float(_NORM.cdf(stat))


def expected_max_sharpe(n_trials: int, sr_trials_std: float) -> float:
    """Seuil de Sharpe attendu sous H0 après `n_trials` essais (multiple testing)."""
    if n_trials < 2 or sr_trials_std <= 0:
        return 0.0
    a = _NORM.inv_cdf(1 - 1.0 / n_trials)
    b = _NORM.inv_cdf(1 - 1.0 / (n_trials * math.e))
    return sr_trials_std * ((1 - _EULER) * a + _EULER * b)


def deflated_sharpe_ratio(returns: np.ndarray, sr_trials: list[float]) -> float:
    """DSR = PSR évalué au seuil déflaté (issu de la dispersion des Sharpe d'essais).

    `sr_trials` = liste des Sharpe (par période) de TOUTES les configs essayées.
    DSR proche de 1 = le résultat survit au multiple testing ; proche de 0 = data-mining.
    """
    arr = np.asarray(sr_trials, float)
    n_trials = arr.size
    sr_std = float(arr.std(ddof=1)) if n_trials > 1 else 0.0
    threshold = expected_max_sharpe(n_trials, sr_std)
    return probabilistic_sharpe_ratio(returns, benchmark_sr=threshold)
