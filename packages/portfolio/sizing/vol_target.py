"""Volatility targeting : taille ∝ 1/volatilité pour viser une vol annualisée cible.

Deux niveaux, non exclusifs :
  1. **Sizer plugin** `VolTarget` (enregistré dans le registre Sizer) — pilote le backtest/live via
     l'interface `Sizer.size(signal, equity, price)`. Kelly bridé (cap sur la fraction du capital).
  2. **Helpers top1pct** (fonctions pures) — vol-target pondéré par la conviction calibrée et les
     multiplicateurs de risque (drawdown scaler × correlation shock), pour la construction de portefeuille.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from packages.portfolio.sizing.registry import sizers


@sizers.register("vol_target")
class VolTarget:
    name = "vol_target"

    def __init__(self, target_annual_vol: float = 0.15, max_capital_frac: float = 0.20,
                 periods_per_year: int = 252) -> None:
        self.target = target_annual_vol
        self.max_frac = max_capital_frac
        self.ppy = periods_per_year

    def size(self, signal, equity, price, regime=None) -> float:
        # vol de l'instrument estimée à partir de l'ATR snapshoté dans le signal
        atr = signal.features.get("atr")
        if not atr or price <= 0:
            return 0.0
        inst_daily_vol = atr / price
        inst_annual_vol = inst_daily_vol * (self.ppy ** 0.5)
        if inst_annual_vol <= 0:
            return 0.0
        capital_frac = min(self.max_frac, self.target / inst_annual_vol)
        return (equity * capital_frac) / price


# --- Helpers top1pct (fonctions pures, construction de portefeuille) -------------------------------

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
