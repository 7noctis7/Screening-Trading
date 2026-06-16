"""Stress test & Monte Carlo — connaître le pire cas AVANT qu'il arrive.

- choc historique/hypothétique : perte si le marché chute de X% (via beta du portefeuille) ;
- Monte Carlo : rééchantillonne les rendements → distribution des drawdowns + proba de ruine.
"""

from __future__ import annotations

import numpy as np


def scenario_loss(portfolio_value: float, shock_pct: float, beta: float = 1.0) -> float:
    """Perte estimée si le marché chute de |shock_pct| (ex. -0.20), via le beta."""
    return float(portfolio_value * shock_pct * beta)


def monte_carlo(returns, horizon: int = 252, n_sims: int = 2000,
                ruin_threshold: float = -0.5, seed: int = 0) -> dict:
    r = np.asarray(returns, float)
    if r.size < 2:
        return {"p_ruin": 0.0, "median_return": 0.0, "var_95_path": 0.0, "worst_dd": 0.0}
    rng = np.random.default_rng(seed)
    finals, max_dds, ruined = [], [], 0
    for _ in range(n_sims):
        path = rng.choice(r, size=horizon, replace=True)
        eq = np.cumprod(1 + path)
        finals.append(eq[-1] - 1)
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak
        max_dds.append(dd.min())
        if dd.min() <= ruin_threshold:
            ruined += 1
    return {"p_ruin": round(ruined / n_sims, 4),
            "median_return": round(float(np.median(finals)), 4),
            "var_95_path": round(float(-np.percentile(finals, 5)), 4),
            "worst_dd": round(float(np.min(max_dds)), 4)}
