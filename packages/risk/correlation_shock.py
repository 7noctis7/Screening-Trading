"""Correlation-shock protocol: when average pairwise correlation spikes
(everything -> 1 = crisis regime), scale exposure down automatically."""
from __future__ import annotations

import numpy as np
import pandas as pd


def mean_pairwise_corr(returns: pd.DataFrame, window: int = 60) -> float:
    c = returns.tail(window).corr().to_numpy()
    n = c.shape[0]
    if n < 2:
        return 0.0
    return float(np.nanmean(c[np.triu_indices(n, k=1)]))


def shock_multiplier(avg_corr: float, warn: float = 0.6, crisis: float = 0.8,
                     floor: float = 0.3) -> float:
    """1.0 below warn; linear to floor at crisis; floor beyond."""
    if avg_corr <= warn:
        return 1.0
    if avg_corr >= crisis:
        return floor
    return 1.0 - (avg_corr - warn) / (crisis - warn) * (1.0 - floor)
