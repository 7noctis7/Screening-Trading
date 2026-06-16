"""Indicateurs de tendance — SMA, EMA, MACD, et régression log-linéaire (z-score).

Anti look-ahead : la valeur à l'index i n'utilise que bars[:i+1]. NaN en warm-up.
"""

from __future__ import annotations

import numpy as np

from packages.indicators.registry import closes, indicators


@indicators.register("sma")
class SMA:
    name = "sma"

    def __init__(self, period: int = 20) -> None:
        self.period = period

    def compute(self, bars) -> list[float]:
        x = np.asarray(closes(bars), float)
        out = np.full(x.size, np.nan)
        if x.size >= self.period:
            c = np.cumsum(np.insert(x, 0, 0.0))
            out[self.period - 1 :] = (c[self.period :] - c[: -self.period]) / self.period
        return out.tolist()


@indicators.register("ema")
class EMA:
    name = "ema"

    def __init__(self, period: int = 20) -> None:
        self.period = period

    def compute(self, bars) -> list[float]:
        x = np.asarray(closes(bars), float)
        out = np.full(x.size, np.nan)
        if x.size == 0:
            return out.tolist()
        alpha = 2.0 / (self.period + 1)
        out[0] = x[0]
        for i in range(1, x.size):
            out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
        # warm-up : invalider avant que la fenêtre soit pleine
        out[: self.period - 1] = np.nan
        return out.tolist()


@indicators.register("loglinreg_z")
class LogLinearRegressionZ:
    """Distance du cours à sa tendance log-linéaire long terme, en z-score.

    Détecte sur/sous-extension et retour à la moyenne (Module 2, étape 1).
    Régression glissante sur `lookback` ; résidu courant normalisé par l'écart-type
    des résidus de la fenêtre.
    """

    name = "loglinreg_z"

    def __init__(self, lookback: int = 120) -> None:
        self.lookback = lookback

    def compute(self, bars) -> list[float]:
        x = np.log(np.asarray(closes(bars), float))
        n = x.size
        out = np.full(n, np.nan)
        L = self.lookback
        t = np.arange(L)
        for i in range(L - 1, n):
            window = x[i - L + 1 : i + 1]
            slope, intercept = np.polyfit(t, window, 1)
            resid = window - (slope * t + intercept)
            sd = resid.std(ddof=1)
            out[i] = resid[-1] / sd if sd > 0 else 0.0
        return out.tolist()


@indicators.register("macd")
class MACD:
    """MACD line (fast EMA - slow EMA). Retourne la ligne MACD."""

    name = "macd"

    def __init__(self, fast: int = 12, slow: int = 26) -> None:
        self.fast = fast
        self.slow = slow

    def compute(self, bars) -> list[float]:
        fast = np.asarray(EMA(self.fast).compute(bars), float)
        slow = np.asarray(EMA(self.slow).compute(bars), float)
        return (fast - slow).tolist()
