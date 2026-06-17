"""Risque avancé — VaR modifiée (Cornish-Fisher), vol EWMA (RiskMetrics), VaR composante.

Best practices buy-side : la VaR gaussienne sous-estime le risque de queue ; la **VaR de
Cornish-Fisher** corrige par l'asymétrie (skew) et l'aplatissement (kurtosis). La **vol EWMA**
réagit vite aux chocs. La **VaR composante** attribue le risque par position. Numpy pur.
"""

from __future__ import annotations

import numpy as np

# Quantiles normaux usuels (évite scipy)
_Z = {0.90: -1.2816, 0.95: -1.6449, 0.975: -1.9600, 0.99: -2.3263}


def ewma_vol(returns, lam: float = 0.94, annualize: int = 252) -> float:
    """Volatilité EWMA (RiskMetrics, λ=0.94) — pondère les chocs récents davantage."""
    r = np.asarray(returns, dtype=float)
    if r.size < 2:
        return 0.0
    w = (1 - lam) * lam ** np.arange(r.size)[::-1]
    w /= w.sum()
    var = float(np.sum(w * (r - r.mean()) ** 2))
    return round((var * annualize) ** 0.5, 6)


def _skew_kurt(r: np.ndarray) -> tuple[float, float]:
    sd = r.std()
    if sd == 0:
        return 0.0, 0.0
    z = (r - r.mean()) / sd
    return float(np.mean(z ** 3)), float(np.mean(z ** 4) - 3.0)


def cornish_fisher_var(returns, alpha: float = 0.95) -> float:
    """VaR modifiée Cornish-Fisher (perte positive) tenant compte de skew/kurtosis."""
    r = np.asarray(returns, dtype=float)
    if r.size < 3:
        return 0.0
    mu, sd = float(r.mean()), float(r.std())
    s, k = _skew_kurt(r)
    z = _Z.get(round(alpha, 3), -1.6449)
    zcf = (z + (z ** 2 - 1) * s / 6 + (z ** 3 - 3 * z) * k / 24
           - (2 * z ** 3 - 5 * z) * s ** 2 / 36)
    return round(max(0.0, -(mu + zcf * sd)), 6)


def component_var(weights, cov, alpha: float = 0.95) -> dict:
    """VaR paramétrique du portefeuille + décomposition par position (somme = VaR totale)."""
    w = np.asarray(weights, dtype=float)
    C = np.asarray(cov, dtype=float)
    if w.size == 0 or C.shape[0] != w.size:
        return {"portfolio_var": 0.0, "component": []}
    port_var = float(w @ C @ w)
    if port_var <= 0:
        return {"portfolio_var": 0.0, "component": [0.0] * w.size}
    vol = port_var ** 0.5
    z = _Z.get(round(alpha, 3), -1.6449)
    pvar = -z * vol                                   # VaR paramétrique (perte positive)
    mctr = (C @ w) / vol                              # contribution marginale à la vol
    comp = (w * mctr) / vol                           # part de chaque position (somme = 1)
    return {"portfolio_var": round(pvar, 6),
            "component": [round(float(pvar * c), 6) for c in comp]}
