"""Indicateurs de momentum — RSI (Wilder), ROC. Anti look-ahead."""

from __future__ import annotations

import numpy as np

from packages.indicators.registry import closes, indicators


@indicators.register("rsi")
class RSI:
    name = "rsi"

    def __init__(self, period: int = 14) -> None:
        self.period = period

    def compute(self, bars) -> list[float]:
        x = np.asarray(closes(bars), float)
        n = x.size
        out = np.full(n, np.nan)
        if n <= self.period:
            return out.tolist()
        delta = np.diff(x)
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_g = gain[: self.period].mean()
        avg_l = loss[: self.period].mean()
        p = self.period
        for i in range(self.period, n):
            if i > self.period:
                avg_g = (avg_g * (p - 1) + gain[i - 1]) / p
                avg_l = (avg_l * (p - 1) + loss[i - 1]) / p
            rs = np.inf if avg_l == 0 else avg_g / avg_l
            out[i] = 100.0 - 100.0 / (1.0 + rs)
        return out.tolist()


@indicators.register("roc")
class ROC:
    name = "roc"

    def __init__(self, period: int = 12) -> None:
        self.period = period

    def compute(self, bars) -> list[float]:
        x = np.asarray(closes(bars), float)
        out = np.full(x.size, np.nan)
        if x.size > self.period:
            out[self.period :] = (x[self.period :] / x[: -self.period] - 1.0) * 100.0
        return out.tolist()
