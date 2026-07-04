"""Câblage du moteur d'alertes en PRODUCTION (hors scripts demo_*).

`default_engine()` assemble les canaux réels selon les clés présentes (Console toujours ;
Telegram/Discord seulement si configurés). `attach_to_bus()` abonne ce moteur à l'event bus
pour que les divergences de réconciliation et les fills partiels de qté inconnue déclenchent
une alerte réelle. Un canal HS n'en bloque jamais un autre (cf. AlertEngine.emit).
"""

from __future__ import annotations

import os

from packages.alerts.engine import AlertEngine
from packages.alerts.handlers import register_on_bus
from packages.alerts.sinks import ConsoleSink, DiscordSink, TelegramSink
from packages.alerts.throttle import Throttle
from packages.common.event_bus import EventBus


def default_engine(throttle: Throttle | None = None) -> AlertEngine:
    """Moteur d'alertes prod : Console toujours + Telegram/Discord si clés présentes en env."""
    sinks: list = [ConsoleSink()]
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        sinks.append(TelegramSink())
    if os.environ.get("DISCORD_WEBHOOK_URL"):
        sinks.append(DiscordSink())
    return AlertEngine(sinks, throttle=throttle)


def attach_to_bus(bus: EventBus, engine: AlertEngine | None = None) -> AlertEngine:
    """Abonne un moteur (par défaut `default_engine()`) aux topics métier de l'event bus."""
    engine = engine or default_engine()
    register_on_bus(engine, bus)
    return engine
