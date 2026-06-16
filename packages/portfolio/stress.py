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


def mc_projection(returns, horizon: int = 252, n_sims: int = 1000,
                  start_value: float = 100.0, seed: int = 0, step: int = 5) -> dict:
    """Éventail Monte Carlo des trajectoires FUTURES (bootstrap des rendements).

    Renvoie les bandes de percentiles (p5 / p25 / médiane / p75 / p95) de la valeur
    projetée du portefeuille sur `horizon` jours → visualisation de l'incertitude.
    """
    r = np.asarray(returns, float)
    if r.size < 2:
        return {"horizon": 0, "steps": [], "p5": [], "p25": [], "p50": [], "p75": [], "p95": []}
    rng = np.random.default_rng(seed)
    paths = start_value * np.cumprod(1 + rng.choice(r, size=(n_sims, horizon), replace=True), axis=1)
    idx = list(range(step - 1, horizon, step))
    if idx[-1] != horizon - 1:
        idx.append(horizon - 1)
    pc = {q: np.percentile(paths[:, idx], q, axis=0) for q in (5, 25, 50, 75, 95)}
    return {
        "horizon": horizon, "steps": [i + 1 for i in idx],
        "p5": [round(float(v), 2) for v in pc[5]], "p25": [round(float(v), 2) for v in pc[25]],
        "p50": [round(float(v), 2) for v in pc[50]], "p75": [round(float(v), 2) for v in pc[75]],
        "p95": [round(float(v), 2) for v in pc[95]],
        "final_p5": round(float(pc[5][-1]), 2), "final_p50": round(float(pc[50][-1]), 2),
        "final_p95": round(float(pc[95][-1]), 2),
    }
