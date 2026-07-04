"""Event bus interne — découple les modules.

Un signal émis n'appelle JAMAIS directement l'exécution (cf. règle d'or 8).
Le screening publie, le portefeuille/risque écoute, l'exécution écoute le
verdict du risque, le journal écoute les fills. Découplage total → testable.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class Event:
    topic: str
    payload: object


Handler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs[topic].append(handler)

    def publish(self, topic: str, payload: object) -> None:
        event = Event(topic=topic, payload=payload)
        for handler in self._subs.get(topic, []):
            handler(event)

    def clear(self) -> None:
        self._subs.clear()


# Topics standard (constantes pour éviter les fautes de frappe)
class Topic:
    SIGNAL_EMITTED = "signal.emitted"
    RISK_APPROVED = "risk.approved"
    RISK_REJECTED = "risk.rejected"
    ORDER_FILLED = "order.filled"
    REGIME_CHANGED = "regime.changed"
    DATA_QUALITY_FAILED = "data.quality_failed"
    KILL_SWITCH = "risk.kill_switch"
    PARTIAL_FILL_UNKNOWN = "execution.partial_fill_unknown"
