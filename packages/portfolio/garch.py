"""GARCH(1,1) — prévision de volatilité conditionnelle (best practice risque de marché).

La vol n'est pas constante : elle se regroupe (volatility clustering). GARCH(1,1) modélise
σ²ₜ = ω + α·r²ₜ₋₁ + β·σ²ₜ₋₁. On estime (α, β) par recherche sur grille avec **variance
targeting** (ω = var·(1−α−β)) en maximisant la vraisemblance gaussienne — numpy pur, sans `arch`.
"""

from __future__ import annotations

import numpy as np


def _neg_loglik(r2: np.ndarray, uncond: float, alpha: float, beta: float) -> float:
    omega = uncond * (1 - alpha - beta)
    s2 = uncond
    ll = 0.0
    for x in r2:
        s2 = omega + alpha * x + beta * s2
        if s2 <= 0:
            return 1e18
        ll += np.log(s2) + x / s2
    return ll


def fit_garch(returns, annualize: int = 252) -> dict:
    """Ajuste un GARCH(1,1) et renvoie params + **vol conditionnelle prévue** (1 pas, annualisée)."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 50:
        return {"available": False}
    r = r - r.mean()
    r2 = r ** 2
    uncond = float(r2.mean()) or 1e-8
    best = (1e18, 0.05, 0.90)
    for alpha in np.linspace(0.02, 0.20, 10):
        for beta in np.linspace(0.70, 0.97, 10):
            if alpha + beta >= 0.999:
                continue
            nll = _neg_loglik(r2, uncond, alpha, beta)
            if nll < best[0]:
                best = (nll, float(alpha), float(beta))
    _, alpha, beta = best
    omega = uncond * (1 - alpha - beta)
    s2 = uncond
    for x in r2:                                   # filtre jusqu'au dernier point
        s2 = omega + alpha * x + beta * s2
    fcast = omega + alpha * r2[-1] + beta * s2     # σ² prévu (pas suivant)
    persistence = alpha + beta
    return {"available": True, "alpha": round(alpha, 3), "beta": round(beta, 3),
            "omega": float(omega), "persistence": round(persistence, 3),
            "forecast_vol": round((fcast * annualize) ** 0.5, 6),
            "uncond_vol": round((uncond * annualize) ** 0.5, 6)}
