"""Fixed-fractional : risquer un % fixe du capital par trade (via la distance au stop)."""

from __future__ import annotations

from packages.portfolio.sizing.registry import risk_per_unit, sizers


@sizers.register("fixed_fractional")
class FixedFractional:
    name = "fixed_fractional"

    def __init__(self, max_risk_pct: float = 0.01) -> None:
        self.max_risk_pct = max_risk_pct

    def size(self, signal, equity, price, regime=None) -> float:
        rpu = risk_per_unit(signal, price)
        if rpu <= 0:
            return 0.0
        qty = (equity * self.max_risk_pct) / rpu
        return max(0.0, qty)
