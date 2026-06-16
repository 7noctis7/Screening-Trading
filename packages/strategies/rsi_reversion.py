"""Stratégie mean-reversion : RSI extrêmes.

Hypothèse : retour à la moyenne dans un range. Favorable en régime 'range'/calme.
Entrée long si RSI < seuil bas, sortie si RSI repasse au-dessus de la médiane.
"""

from __future__ import annotations

from packages.core.models import Signal, SignalDirection
from packages.indicators.momentum import RSI
from packages.indicators.volatility import ATR
from packages.strategies.registry import strategies


@strategies.register("rsi_reversion")
class RsiReversion:
    name = "rsi_reversion"
    favorable_regime = "range"

    def __init__(self, period: int = 14, low: float = 30.0, exit_level: float = 55.0,
                 atr_period: int = 14, atr_stop: float = 2.0, rr: float = 2.0) -> None:
        self.period, self.low, self.exit_level = period, low, exit_level
        self.atr_period, self.atr_stop, self.rr = atr_period, atr_stop, rr

    def generate_signals(self, bars, regime=None) -> list[Signal]:
        if len(bars) < self.period + 2:
            return []
        r = RSI(self.period).compute(bars)
        a = ATR(self.atr_period).compute(bars)
        i = len(bars) - 1
        if any(v != v for v in (r[i], r[i - 1], a[i])):
            return []
        price, atr = bars[i].close, a[i]
        if r[i - 1] >= self.low and r[i] < self.low:
            stop = price - self.atr_stop * atr
            target = price + self.rr * self.atr_stop * atr
            return [Signal(bars[i].instrument, SignalDirection.LONG, self.name,
                           bars[i].ts, 1.0, stop, target, "RSI oversold",
                           {"rsi": r[i], "atr": atr})]
        if r[i - 1] < self.exit_level <= r[i]:
            return [Signal(bars[i].instrument, SignalDirection.FLAT, self.name,
                           bars[i].ts, 1.0, reason="RSI mean revert exit")]
        return []
