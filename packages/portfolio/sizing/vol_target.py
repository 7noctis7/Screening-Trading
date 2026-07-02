"""Volatility-targeting position size, modulated by calibrated conviction
and by the risk multipliers (drawdown scaler x correlation shock)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def realized_vol(prices: pd.Series, window: int = 20, ann: int = 252) -> float:
    r = prices.pct_change().dropna().tail(window)
    return float(r.std() * np.sqrt(ann))


def vol_target_weight(asset_vol: float, target_vol: float = 0.10,
                      max_weight: float = 0.20) -> float:
    if asset_vol <= 0:
        return 0.0
    return float(min(target_vol / asset_vol, max_weight))


def conviction_multiplier(p_calibrated: float, p0: float = 0.5,
                          slope: float = 4.0, lo: float = 0.25,
                          hi: float = 1.5) -> float:
    """Calibrated win probability -> bounded size multiplier."""
    return float(np.clip(1.0 + slope * (p_calibrated - p0), lo, hi))


def final_weight(asset_vol: float, p_calibrated: float, dd_mult: float,
                 corr_mult: float, target_vol: float = 0.10,
                 max_weight: float = 0.20) -> float:
    base = vol_target_weight(asset_vol, target_vol, max_weight)
    return base * conviction_multiplier(p_calibrated) * dd_mult * corr_mult
