"""EVT — théorie des valeurs extrêmes (Peaks-Over-Threshold + loi de Pareto généralisée).

Pour le risque de queue extrême (VaR 99,9 %), l'hypothèse gaussienne échoue. On modélise les
dépassements au-delà d'un seuil par une **GPD** (estimée par méthode des moments) → VaR & ES
extrêmes. Référence : McNeil/Frey/Embrechts. Numpy pur, testable hors-ligne.
"""

from __future__ import annotations

import numpy as np


def fit_pot(returns, threshold_q: float = 0.95) -> dict:
    """Ajuste une GPD aux pertes au-delà du quantile `threshold_q` (Peaks-Over-Threshold)."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    losses = -r                                   # pertes positives
    if losses.size < 50:
        return {"available": False}
    u = float(np.quantile(losses, threshold_q))
    exc = losses[losses > u] - u
    if exc.size < 10:
        return {"available": False}
    m, v = float(exc.mean()), float(exc.var())
    if v <= 0:
        return {"available": False}
    xi = 0.5 * (1 - m * m / v)                     # méthode des moments (shape)
    beta = 0.5 * m * (m * m / v + 1)              # scale
    return {"available": True, "u": u, "xi": round(xi, 4), "beta": round(beta, 6),
            "n": int(losses.size), "n_exc": int(exc.size), "threshold_q": threshold_q}


def evt_var_es(returns, alpha: float = 0.999, threshold_q: float = 0.95) -> dict:
    """VaR & Expected Shortfall extrêmes via GPD (pertes positives)."""
    fit = fit_pot(returns, threshold_q)
    if not fit.get("available"):
        return {"available": False}
    xi, beta, u = fit["xi"], fit["beta"], fit["u"]
    n, n_exc = fit["n"], fit["n_exc"]
    if xi >= 1 or n_exc == 0:
        return {"available": False}
    ratio = (n / n_exc) * (1 - alpha)
    if ratio <= 0:
        return {"available": False}
    if abs(xi) < 1e-6:
        var = u - beta * np.log(ratio)
    else:
        var = u + (beta / xi) * (ratio ** (-xi) - 1)
    es = (var + beta - xi * u) / (1 - xi)
    return {"available": True, "alpha": alpha, "xi": xi,
            "var": round(float(max(0.0, var)), 6), "es": round(float(max(0.0, es)), 6)}
