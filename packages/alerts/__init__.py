"""packages.alerts — moteur d'alertes multi-canal, hiérarchisé, anti-spam, traçable."""
from packages.alerts.engine import AlertEngine
from packages.alerts.handlers import register_on_bus
from packages.alerts.models import Alert, Severity
from packages.alerts.sinks import (
    ConsoleSink, DiscordSink, InMemorySink, TelegramSink, format_message,
)
from packages.alerts.throttle import Throttle

__all__ = [
    "AlertEngine", "Alert", "Severity", "Throttle", "register_on_bus",
    "InMemorySink", "ConsoleSink", "TelegramSink", "DiscordSink", "format_message",
]
