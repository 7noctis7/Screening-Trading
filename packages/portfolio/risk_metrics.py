"""VaR / CVaR (historique + paramétrique) — esprit FRM (Jorion). Pures, testables.

Convention : pertes en POSITIF (VaR 5% = perte telle qu'on fait pire 5% du temps).
"""

from __future__ import annotations

from statistics import NormalDist

import numpy as np


def var_historical(returns, alpha: float = 0.95) -> float:
    r = np.asarray(returns, float)
    if r.size == 0:
        return 0.0
    return float(-np.percentile(r, (1 - alpha) * 100))


def cvar_historical(returns, alpha: float = 0.95) -> float:
    r = np.asarray(returns, float)
    if r.size == 0:
        return 0.0
    thr = -var_historical(r, alpha)
    tail = r[r <= thr]
    return float(-tail.mean()) if tail.size else var_historical(r, alpha)


def var_parametric(returns, alpha: float = 0.95) -> float:
    r = np.asarray(returns, float)
    if r.size < 2:
        return 0.0
    z = NormalDist().inv_cdf(1 - alpha)
    return float(-(r.mean() + z * r.std(ddof=1)))


def risk_metrics(returns, alpha: float = 0.95) -> dict:
    return {"var_95": round(var_historical(returns, alpha), 5),
            "cvar_95": round(cvar_historical(returns, alpha), 5),
            "var_param_95": round(var_parametric(returns, alpha), 5),
            "vol": round(float(np.std(np.asarray(returns, float), ddof=1)), 5)
            if len(returns) > 1 else 0.0}
