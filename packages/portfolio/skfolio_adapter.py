"""Adaptateur **skfolio** (optionnel, gratuit, compatible scikit-learn) → optimiseurs de
portefeuille de qualité recherche. Import paresseux : si skfolio n'est pas installé, on renvoie
None et le code appelant retombe sur nos optimiseurs numpy (HRP/min-var/ERC).

Installation : `pip install skfolio`. Méthodes exposées : min_risk, max_diversification, max_sharpe,
hrp (hierarchical risk parity).
"""

from __future__ import annotations

import numpy as np


def skfolio_available() -> bool:
    try:
        import skfolio  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def skfolio_weights(returns_matrix, method: str = "max_diversification") -> list[float] | None:
    """Poids long-only normalisés via skfolio. `returns_matrix` : array (T × n) de rendements.

    Renvoie None si skfolio indisponible ou en cas d'échec (le caller gère le repli).
    """
    try:
        import pandas as pd
        from skfolio.optimization import (HierarchicalRiskParity, MaximumDiversification,
                                          MeanRisk, ObjectiveFunction)
    except Exception:  # noqa: BLE001
        return None
    try:
        X = pd.DataFrame(np.asarray(returns_matrix, dtype=float))
        if X.shape[0] < 10 or X.shape[1] < 2:
            return None
        if method == "hrp":
            model = HierarchicalRiskParity()
        elif method == "min_risk":
            model = MeanRisk(objective_function=ObjectiveFunction.MINIMIZE_RISK)
        elif method == "max_sharpe":
            model = MeanRisk(objective_function=ObjectiveFunction.MAXIMIZE_RATIO)
        else:
            model = MaximumDiversification()
        model.fit(X)
        w = np.asarray(model.weights_, dtype=float).ravel()
        w = np.clip(w, 0.0, None)
        s = w.sum()
        return [round(float(x), 4) for x in (w / s)] if s > 0 else None
    except Exception:  # noqa: BLE001
        return None
