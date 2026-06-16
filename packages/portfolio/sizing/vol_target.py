"""Volatility targeting : taille ∝ 1/volatilité pour viser une vol annualisée cible.

Kelly bridé inclus en option (cap sur la fraction du capital). Jamais 'tout-in'.
"""

from __future__ import annotations

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
