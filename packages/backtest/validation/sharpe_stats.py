"""Probabilistic Sharpe Ratio, Deflated Sharpe, Minimum Track Record Length.
Refs: Bailey & Lopez de Prado (2012, 2014). Frequencies: per-period SR in,
same convention throughout (do NOT mix annualized and per-period)."""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

EULER_GAMMA = 0.5772156649015329


def sr_moments(returns: np.ndarray) -> tuple[float, float, float, int]:
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    sr = r.mean() / r.std(ddof=1)
    skew = float(((r - r.mean()) ** 3).mean() / r.std(ddof=0) ** 3)
    kurt = float(((r - r.mean()) ** 4).mean() / r.std(ddof=0) ** 4)
    return float(sr), skew, kurt, len(r)


def psr(sr: float, skew: float, kurt: float, n: int, sr_star: float = 0.0) -> float:
    """P(true SR > sr_star). Wants > 0.95."""
    denom = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4 * sr**2, 1e-12))
    return float(norm.cdf((sr - sr_star) * math.sqrt(n - 1) / denom))


def expected_max_sr(n_trials: int, var_sr: float) -> float:
    """E[max SR] across n_trials of zero-skill strategies -> DSR benchmark."""
    if n_trials < 2:
        return 0.0
    e = (1 - EULER_GAMMA) * norm.ppf(1 - 1 / n_trials) \
        + EULER_GAMMA * norm.ppf(1 - 1 / (n_trials * math.e))
    return float(math.sqrt(var_sr) * e)


def deflated_sr(returns: np.ndarray, n_trials: int, var_sr_across_trials: float) -> float:
    """PSR against the expected-max-SR benchmark. > 0.95 = likely real."""
    sr, skew, kurt, n = sr_moments(returns)
    sr_star = expected_max_sr(n_trials, var_sr_across_trials)
    return psr(sr, skew, kurt, n, sr_star)


def min_trl(sr: float, skew: float, kurt: float, sr_star: float = 0.0,
            alpha: float = 0.05) -> float:
    """Minimum track record length (periods) so PSR > 1-alpha.
    Gates the paper -> live decision objectively."""
    if sr <= sr_star:
        return float("inf")
    z = norm.ppf(1 - alpha)
    return 1 + (1 - skew * sr + (kurt - 1) / 4 * sr**2) * (z / (sr - sr_star)) ** 2
