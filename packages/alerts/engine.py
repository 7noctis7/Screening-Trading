"""Moteur d'alertes — route vers les canaux selon la sévérité, applique le throttling.

Un seul point d'émission (`emit`) ; chaque canal filtre par sévérité minimale.
Toutes les alertes sont tracées (historique) pour l'audit.
"""

from __future__ import annotations

from packages.alerts.models import Alert, Severity
from packages.alerts.throttle import Throttle
from packages.common.logging import get_logger

log = get_logger("alerts.engine")


class AlertEngine:
    def __init__(self, sinks: list, throttle: Throttle | None = None) -> None:
        self.sinks = sinks
        self.throttle = throttle or Throttle()
        self.history: list[Alert] = []

    def emit(self, alert: Alert) -> bool:
        """Émet une alerte ; renvoie False si throttlée (doublon récent)."""
        if not self.throttle.allow(alert.key()):
            return False
        self.history.append(alert)
        log.info("alerte", extra={"extra": {
            "kind": alert.kind, "severity": alert.severity.name, "msg": alert.message}})
        for sink in self.sinks:
            if alert.severity >= getattr(sink, "min_severity", Severity.INFO):
                try:
                    sink.send(alert)
                except Exception as e:  # noqa: BLE001 — un canal HS ne bloque pas les autres
                    log.warning("canal en échec", extra={"extra": {
                        "sink": getattr(sink, "name", "?"), "err": str(e)[:120]}})
        return True
