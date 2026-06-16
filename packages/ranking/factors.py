"""Facteurs cross-sectional — interface unifiée à CONTEXTE.

Chaque facteur expose `values(ctx) -> {symbol: raw}` (NaN si indisponible).
Le moteur normalise ensuite en z-score (global ou sector-neutral) puis pondère.
Ainsi facteurs TECHNIQUES (depuis les prix) et FONDAMENTAUX (depuis les états
financiers) partagent la même mécanique. `sector_neutral=True` → z-score intra-secteur.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from packages.core.registry import Registry

factor_calcs: Registry = Registry("factor_calc")


@dataclass
class FactorContext:
    panel: dict[str, list]                      # symbol -> [Bar]
    t: int = 10**9                              # index temporel (info <= t)
    fundamentals: dict | None = None            # symbol -> Financials
    sector: dict[str, str] = field(default_factory=dict)


def _closes(bars, t):
    return np.asarray([b.close for b in bars[: t + 1]], float)


@factor_calcs.register("momentum")
class Momentum:
    name = "momentum"
    sector_neutral = False

    def __init__(self, lookback: int = 252, skip: int = 21) -> None:
        self.lookback, self.skip = lookback, skip

    def values(self, ctx: FactorContext) -> dict[str, float]:
        out = {}
        for sym, bars in ctx.panel.items():
            c = _closes(bars, min(ctx.t, len(bars) - 1))
            out[sym] = (float(c[-1 - self.skip] / c[-self.lookback] - 1.0)
                        if c.size >= self.lookback + 1 else float("nan"))
        return out


@factor_calcs.register("trend")
class Trend:
    name = "trend"
    sector_neutral = False

    def __init__(self, window: int = 200) -> None:
        self.window = window

    def values(self, ctx: FactorContext) -> dict[str, float]:
        out = {}
        for sym, bars in ctx.panel.items():
            c = _closes(bars, min(ctx.t, len(bars) - 1))
            out[sym] = (float(c[-1] / c[-self.window:].mean() - 1.0)
                        if c.size >= self.window else float("nan"))
        return out


@factor_calcs.register("low_vol")
class LowVol:
    name = "low_vol"
    sector_neutral = False

    def __init__(self, window: int = 63) -> None:
        self.window = window

    def values(self, ctx: FactorContext) -> dict[str, float]:
        out = {}
        for sym, bars in ctx.panel.items():
            c = _closes(bars, min(ctx.t, len(bars) - 1))
            if c.size < self.window + 1:
                out[sym] = float("nan")
            else:
                rets = np.diff(np.log(c[-self.window - 1:]))
                out[sym] = float(-rets.std(ddof=1))
        return out
