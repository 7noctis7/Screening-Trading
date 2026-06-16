"""Handlers — 1 type d'événement = 1 constructeur d'alerte. Abonnement à l'event bus.

Traduit les événements métier (régime, risque, données, exécution) en alertes
hiérarchisées. Le découplage passe par l'event bus : les modules publient, on écoute.
"""

from __future__ import annotations

from packages.alerts.models import Alert, Severity
from packages.common.event_bus import EventBus, Topic


def on_regime_changed(payload: dict) -> Alert:
    sev = Severity.WARNING if payload.get("to") in ("risk_off", "recession") else Severity.INFO
    return Alert("regime", sev,
                 f"Régime → {payload.get('to')} (était {payload.get('from')})",
                 dedup_key=f"regime:{payload.get('to')}", data=payload)


def on_kill_switch(payload: dict) -> Alert:
    return Alert("risk", Severity.CRITICAL,
                 f"KILL-SWITCH déclenché (drawdown {payload.get('drawdown', '?')})",
                 dedup_key="risk:kill_switch", data=payload)


def on_risk_rejected(payload: dict) -> Alert:
    return Alert("risk", Severity.WARNING,
                 f"Ordre rejeté par le risque : {payload.get('reason', '?')}", data=payload)


def on_data_quality_failed(payload: dict) -> Alert:
    return Alert("data", Severity.WARNING,
                 f"Contrôle qualité échoué : {payload.get('detail', payload)}",
                 dedup_key=f"data:{payload.get('symbol', '')}", data=payload)


def on_order_filled(payload: dict) -> Alert:
    return Alert("execution", Severity.INFO,
                 f"Fill {payload.get('side', '')} {payload.get('symbol', '')} "
                 f"x{payload.get('qty', '')}", data=payload)


def on_reconcile_divergence(payload: dict) -> Alert:
    return Alert("execution", Severity.CRITICAL,
                 f"Divergence broker↔DB : {payload.get('divergences', payload)}",
                 dedup_key="execution:divergence", data=payload)


def register_on_bus(engine, bus: EventBus) -> None:
    """Abonne le moteur d'alertes aux topics de l'event bus."""
    mapping = {
        Topic.REGIME_CHANGED: on_regime_changed,
        Topic.KILL_SWITCH: on_kill_switch,
        Topic.RISK_REJECTED: on_risk_rejected,
        Topic.DATA_QUALITY_FAILED: on_data_quality_failed,
        Topic.ORDER_FILLED: on_order_filled,
        "execution.reconcile_divergence": on_reconcile_divergence,
    }
    for topic, builder in mapping.items():
        bus.subscribe(topic, lambda ev, b=builder: engine.emit(b(ev.payload)))
