"""Stratégie trend-following : croisement de moyennes mobiles.

Hypothèse : les tendances persistent. Favorable en régime 'trending'.
Entrée long au croisement haussier (fast > slow), sortie au croisement baissier.
Stop ATR-based, target = R:R via multiple d'ATR.
"""

from __future__ import annotations

from packages.core.models import Signal, SignalDirection
from packages.indicators.trend import SMA
from packages.indicators.volatility import ATR
from packages.strategies.registry import strategies


@strategies.register("ma_crossover")
class MaCrossover:
    name = "ma_crossover"
    favorable_regime = "trending"

    def __init__(self, fast: int = 20, slow: int = 50, atr_period: int = 14,
                 atr_stop: float = 2.0, rr: float = 2.5) -> None:
        self.fast, self.slow = fast, slow
        self.atr_period, self.atr_stop, self.rr = atr_period, atr_stop, rr

    def generate_signals(self, bars, regime=None) -> list[Signal]:
        if len(bars) < self.slow + 1:
            return []
        f = SMA(self.fast).compute(bars)
        s = SMA(self.slow).compute(bars)
        a = ATR(self.atr_period).compute(bars)
        i = len(bars) - 1
        if any(v != v for v in (f[i], s[i], f[i - 1], s[i - 1], a[i])):  # NaN
            return []
        price, atr = bars[i].close, a[i]
        crossed_up = f[i - 1] <= s[i - 1] and f[i] > s[i]
        crossed_down = f[i - 1] >= s[i - 1] and f[i] < s[i]
        if crossed_up:
            stop = price - self.atr_stop * atr
            target = price + self.rr * self.atr_stop * atr
            return [Signal(bars[i].instrument, SignalDirection.LONG, self.name,
                           bars[i].ts, 1.0, stop, target, "fast>slow cross",
                           {"sma_fast": f[i], "sma_slow": s[i], "atr": atr})]
        if crossed_down:
            return [Signal(bars[i].instrument, SignalDirection.FLAT, self.name,
                           bars[i].ts, 1.0, reason="fast<slow cross")]
        return []
