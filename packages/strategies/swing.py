"""Stratégie SWING trading : achat de repli (pullback) dans une tendance haussière.

Hypothèse : en tendance haussière, les replis se rachètent. On combine un FILTRE de
tendance (SMA lente montante + cours au-dessus) et un déclencheur de REPLI (RSI qui
remonte depuis une zone basse) → entrées plus fréquentes et meilleur taux de présence
en marché que le simple croisement, avec sorties sur surchauffe RSI ou cassure de
tendance. Stop/target ancrés sur l'ATR. Favorable en régime 'trending'/'expansion'.
"""

from __future__ import annotations

from packages.core.models import Signal, SignalDirection
from packages.indicators.momentum import RSI
from packages.indicators.trend import SMA
from packages.indicators.volatility import ATR
from packages.strategies.registry import strategies


@strategies.register("swing")
class Swing:
    name = "swing"
    favorable_regime = "trending"

    def __init__(self, trend: int = 50, slope_lookback: int = 5, rsi_period: int = 14,
                 pullback: float = 45.0, exit_level: float = 68.0, atr_period: int = 14,
                 atr_stop: float = 2.5, rr: float = 3.0) -> None:
        self.trend, self.slope_lookback = trend, slope_lookback
        self.rsi_period, self.pullback, self.exit_level = rsi_period, pullback, exit_level
        self.atr_period, self.atr_stop, self.rr = atr_period, atr_stop, rr

    def generate_signals(self, bars, regime=None) -> list[Signal]:
        need = max(self.trend, self.rsi_period, self.atr_period) + self.slope_lookback + 1
        if len(bars) < need:
            return []
        sma = SMA(self.trend).compute(bars)
        rsi = RSI(self.rsi_period).compute(bars)
        atr = ATR(self.atr_period).compute(bars)
        i = len(bars) - 1
        j = i - self.slope_lookback
        if any(v != v for v in (sma[i], sma[j], rsi[i], rsi[i - 1], atr[i])):  # NaN
            return []
        price = bars[i].close
        uptrend = price > sma[i] and sma[i] > sma[j]               # tendance haussière
        pullback_done = rsi[i - 1] < self.pullback <= rsi[i]       # repli racheté
        if uptrend and pullback_done:
            stop = price - self.atr_stop * atr[i]
            target = price + self.rr * self.atr_stop * atr[i]
            return [Signal(bars[i].instrument, SignalDirection.LONG, self.name,
                           bars[i].ts, 1.0, stop, target, "pullback en tendance",
                           {"sma": sma[i], "rsi": rsi[i], "atr": atr[i]})]
        # sortie : surchauffe RSI (prise de profit) ou cassure de tendance
        if (rsi[i - 1] >= self.exit_level > rsi[i]) or price < sma[i]:
            return [Signal(bars[i].instrument, SignalDirection.FLAT, self.name,
                           bars[i].ts, 1.0, reason="RSI haut / cassure tendance")]
        return []
