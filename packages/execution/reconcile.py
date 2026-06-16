"""Réconciliation positions broker ↔ état interne (DB). Alerte sur divergence.

À lancer quotidiennement (ou après chaque session). Une divergence = bug, fill manqué
ou action hors-système → à investiguer avant de continuer à trader.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.core.models import Position
from packages.common.event_bus import EventBus


@dataclass
class Divergence:
    instrument: str
    broker_qty: float
    internal_qty: float

    @property
    def diff(self) -> float:
        return self.broker_qty - self.internal_qty


@dataclass
class ReconResult:
    divergences: list[Divergence] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.divergences


def reconcile(broker_positions: list[Position], internal_positions: list[Position],
              tol: float = 1e-6, bus: EventBus | None = None) -> ReconResult:
    b = {p.instrument: p.qty for p in broker_positions}
    i = {p.instrument: p.qty for p in internal_positions}
    result = ReconResult()
    for sym in set(b) | set(i):
        bq, iq = b.get(sym, 0.0), i.get(sym, 0.0)
        if abs(bq - iq) > tol:
            result.divergences.append(Divergence(sym, bq, iq))
    if not result.ok and bus is not None:
        bus.publish("execution.reconcile_divergence",
                    {"divergences": [(d.instrument, d.diff) for d in result.divergences]})
    return result
