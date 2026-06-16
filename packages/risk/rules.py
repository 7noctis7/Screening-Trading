"""Règles de risque à droit de veto. 1 règle = 1 classe (regroupées ici v1).

Chaque règle reçoit l'ordre + l'état du portefeuille et renvoie une RiskDecision.
Le RiskEngine les enchaîne : un seul veto suffit à bloquer.
"""

from __future__ import annotations

from packages.core.interfaces import RiskDecision
from packages.core.models import Order
from packages.core.registry import Registry

risk_rules: Registry = Registry("risk_rule")


@risk_rules.register("reward_risk")
class RewardRiskRule:
    """Refuse les setups sous le R:R minimal (calculé entrée/stop/target)."""

    name = "reward_risk"

    def __init__(self, min_rr: float = 2.0) -> None:
        self.min_rr = min_rr

    def check(self, order: Order, positions, equity, regime=None, *, signal=None):
        if signal is None or signal.stop is None or signal.target is None:
            return RiskDecision.ok()
        entry = order.limit_price or signal.features.get("ref_price")
        if entry is None:
            return RiskDecision.ok()
        risk = abs(entry - signal.stop)
        if risk == 0:
            return RiskDecision.veto("stop == entrée (risque nul)")
        rr = abs(signal.target - entry) / risk
        if rr < self.min_rr:
            return RiskDecision.veto(f"R:R {rr:.2f} < {self.min_rr}")
        return RiskDecision.ok()


@risk_rules.register("max_positions")
class MaxPositionsRule:
    name = "max_positions"

    def __init__(self, max_positions: int = 20) -> None:
        self.max_positions = max_positions

    def check(self, order, positions, equity, regime=None, *, signal=None):
        held = {p.instrument for p in positions}
        if order.instrument in held:
            return RiskDecision.ok()
        if len(held) >= self.max_positions:
            return RiskDecision.veto(f"{len(held)} positions ≥ max {self.max_positions}")
        return RiskDecision.ok()


@risk_rules.register("max_exposure_per_asset")
class MaxExposurePerAssetRule:
    name = "max_exposure_per_asset"

    def __init__(self, max_pct: float = 0.10) -> None:
        self.max_pct = max_pct

    def check(self, order, positions, equity, regime=None, *, signal=None):
        price = order.limit_price or (signal.features.get("ref_price") if signal else None)
        if price is None or equity <= 0:
            return RiskDecision.ok()
        notional = abs(order.qty) * price
        if notional / equity > self.max_pct:
            return RiskDecision.veto(
                f"expo actif {notional / equity:.1%} > {self.max_pct:.0%}")
        return RiskDecision.ok()
