"""Indicateurs de volatilité — ATR (Wilder), largeur de bandes de Bollinger."""

from __future__ import annotations

import numpy as np

from packages.indicators.registry import closes, indicators


@indicators.register("atr")
class ATR:
    name = "atr"

    def __init__(self, period: int = 14) -> None:
        self.period = period

    def compute(self, bars) -> list[float]:
        h = np.asarray([b.high for b in bars], float)
        low = np.asarray([b.low for b in bars], float)
        c = np.asarray(closes(bars), float)
        n = c.size
        out = np.full(n, np.nan)
        if n < 2:
            return out.tolist()
        prev_c = np.concatenate([[c[0]], c[:-1]])
        tr = np.maximum.reduce([h - low, np.abs(h - prev_c), np.abs(low - prev_c)])
        if n <= self.period:
            return out.tolist()
        atr = tr[1 : self.period + 1].mean()
        out[self.period] = atr
        for i in range(self.period + 1, n):
            atr = (atr * (self.period - 1) + tr[i]) / self.period
            out[i] = atr
        return out.tolist()


@indicators.register("bbwidth")
class BollingerWidth:
    """Largeur des bandes (haut-bas) / médiane — proxy de compression/expansion."""

    name = "bbwidth"

    def __init__(self, period: int = 20, k: float = 2.0) -> None:
        self.period = period
        self.k = k

    def compute(self, bars) -> list[float]:
        x = np.asarray(closes(bars), float)
        n = x.size
        out = np.full(n, np.nan)
        for i in range(self.period - 1, n):
            w = x[i - self.period + 1 : i + 1]
            ma, sd = w.mean(), w.std(ddof=0)
            out[i] = (2 * self.k * sd) / ma if ma else np.nan
        return out.tolist()
