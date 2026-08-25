"""Risk engine du moteur ÉVÉNEMENTIEL — couche bloquante + kill-switch drawdown quotidien.

Enchaîne les règles (veto = stop). Surveille le drawdown intraday : au-delà du
seuil, le kill-switch s'arme et refuse toute nouvelle entrée jusqu'au reset.

PÉRIMÈTRE, décidé et documenté le 25/08 (ADR : docs/DECISIONS.md).

Ce moteur raisonne PAR SIGNAL et PAR STOP, barre après barre : `approve(order, positions,
equity, regime, signal)` suppose qu'il existe un ordre unitaire, un signal qui l'a produit, et
un stop qui le borne. C'est la sémantique de `LiveEngine` (streaming) et des backtests
événementiels — `scripts/demo_*.py`, `packages/backtest/engine.py`.

IL N'EST PAS, ET NE DOIT PAS ÊTRE, BRANCHÉ SUR LE RÉÉQUILIBRAGE. `scripts/run_live.py`
réconcilie un portefeuille CIBLE en une passe : il n'a ni signal, ni stop, ni barre. L'y
brancher exigerait de fabriquer des objets `Order` et `signal` factices pour satisfaire une
interface conçue pour autre chose — et un adaptateur factice au milieu d'une barrière de
sécurité est exactement ce qu'on ne veut pas. On obtiendrait DEUX vérités sur le risque là où
il en faut une.

Le chemin de rééquilibrage a sa propre barrière, adaptée à sa sémantique :
`packages/risk/order_gate.py` — elle ne voit qu'un ordre, un état de compte et des limites
lues dans l'environnement, et c'est cette pauvreté d'interface qui la rend non contournable.

Autrement dit, l'absence de `RiskEngine` dans `run_live.py` est un CHOIX, pas un oubli. Un test
d'architecture le fixe (`tests/risk/test_perimetres.py`) : si quelqu'un l'y branche un jour, ce
sera délibérément, pas par accident.
"""

from __future__ import annotations

from packages.common.event_bus import EventBus, Topic
from packages.core.interfaces import RiskDecision


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
