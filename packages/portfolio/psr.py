"""Sharpe probabiliste & déflaté (López de Prado) — anti-surapprentissage de backtest.

Un Sharpe élevé peut être un artefact (échantillon court, queues épaisses, **essais multiples**).
- **PSR** : probabilité que le vrai Sharpe dépasse un seuil, corrigée de skew/kurtosis.
- **DSR** : PSR avec un seuil relevé pour le nombre d'essais (multiple testing) → garde-fou clé.
stdlib (math), testable hors-ligne.
"""

from __future__ import annotations

import math


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Quantile normal (approx. Acklam) pour p ∈ (0,1)."""
    p = min(1 - 1e-9, max(1e-9, p))
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def probabilistic_sharpe_ratio(sharpe: float, n: int, skew: float = 0.0,
                               kurt: float = 3.0, sr_benchmark: float = 0.0) -> float:
    """PSR : P(SR_vrai > sr_benchmark). Sharpe et seuil sur la MÊME périodicité."""
    if n < 2:
        return 0.0
    denom = math.sqrt(max(1e-12, 1 - skew * sharpe + (kurt - 1) / 4.0 * sharpe ** 2))
    return round(_norm_cdf((sharpe - sr_benchmark) * math.sqrt(n - 1) / denom), 4)


def deflated_sharpe_ratio(sharpe: float, n: int, n_trials: int,
                          skew: float = 0.0, kurt: float = 3.0,
                          sr_std: float = 1.0) -> float:
    """DSR : PSR avec seuil relevé pour `n_trials` essais (Bailey & López de Prado)."""
    if n_trials < 1 or n < 2:
        return 0.0
    e = 0.5772156649                                  # Euler-Mascheroni
    # seuil de Sharpe attendu sous H0 par le maximum de n_trials essais
    z1 = _norm_ppf(1 - 1.0 / n_trials)
    z2 = _norm_ppf(1 - 1.0 / (n_trials * math.e))
    sr_star = sr_std * ((1 - e) * z1 + e * z2)
    return probabilistic_sharpe_ratio(sharpe, n, skew, kurt, sr_benchmark=sr_star)
