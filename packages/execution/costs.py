"""Modèle de coûts réalistes : frais (bps) + slippage (bps). Dès le backtest."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CostModel:
    fee_bps: float = 5.0       # commission
    slippage_bps: float = 2.0  # impact/spread

    def apply_buy(self, price: float) -> float:
        return price * (1 + self.slippage_bps / 1e4)

    def apply_sell(self, price: float) -> float:
        return price * (1 - self.slippage_bps / 1e4)

    def fee(self, notional: float) -> float:
        return abs(notional) * self.fee_bps / 1e4
