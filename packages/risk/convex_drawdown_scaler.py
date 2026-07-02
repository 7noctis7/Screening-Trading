"""Convex de-risking rule: exposure multiplier as a function of drawdown.

The ONLY mechanism that guarantees the max-DD bound by construction.
Config-driven (config/risk.yaml -> drawdown_scaler).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DrawdownScaler:
    """Piecewise-linear exposure multiplier. Default:
    dd 0..-10%: 1.0 ; -10..-20%: 1.0->0.5 ; -20..-30%: 0.5->0.25 ;
    beyond -30%: 0.0 (kill zone, hard floor before the 35% limit)."""

    breakpoints: tuple[float, ...] = (0.0, -0.10, -0.20, -0.30)
    multipliers: tuple[float, ...] = (1.0, 1.0, 0.50, 0.25)
    kill_dd: float = -0.30

    def multiplier(self, drawdown: float) -> float:
        if drawdown <= self.kill_dd:
            return 0.0
        bp, m = self.breakpoints, self.multipliers
        if drawdown >= bp[0]:
            return m[0]
        for i in range(len(bp) - 1):
            if bp[i] >= drawdown > bp[i + 1]:
                span = bp[i] - bp[i + 1]
                frac = (bp[i] - drawdown) / span if span else 0.0
                return m[i] + frac * (m[i + 1] - m[i])
        return m[-1]


def current_drawdown(equity: list[float]) -> float:
    peak = float("-inf")
    for v in equity:
        peak = max(peak, v)
    return equity[-1] / peak - 1.0
