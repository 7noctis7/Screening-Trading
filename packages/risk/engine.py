"""Risk engine — couche bloquante + kill-switch drawdown quotidien.

Enchaîne les règles (veto = stop). Surveille le drawdown intraday : au-delà du
seuil, le kill-switch s'arme et refuse toute nouvelle entrée jusqu'au reset.
"""

from __future__ import annotations

from packages.core.interfaces import RiskDecision
from packages.common.event_bus import EventBus, Topic


class RiskEngine:
    def __init__(self, rules, max_daily_drawdown_pct: float = 0.05,
                 bus: EventBus | None = None) -> None:
        self.rules = list(rules)
        self.max_dd = max_daily_drawdown_pct
        self.bus = bus
        self._day_start_equity: float | None = None
        self.kill_switch = False

    def new_day(self, equity: float) -> None:
        self._day_start_equity = equity
        self.kill_switch = False

    def mark_equity(self, equity: float) -> None:
        if self._day_start_equity is None:
            self._day_start_equity = equity
        dd = 1 - equity / self._day_start_equity
        if dd >= self.max_dd and not self.kill_switch:
            self.kill_switch = True
            if self.bus:
                self.bus.publish(Topic.KILL_SWITCH, {"drawdown": dd})

    def approve(self, order, positions, equity, regime=None, signal=None) -> RiskDecision:
        if self.kill_switch:
            return RiskDecision.veto("kill-switch armé (drawdown quotidien)")
        for rule in self.rules:
            decision = rule.check(order, positions, equity, regime, signal=signal)
            if not decision.approved:
                if self.bus:
                    self.bus.publish(Topic.RISK_REJECTED,
                                     {"rule": rule.name, "reason": decision.reason})
                return decision
        return RiskDecision.ok()
