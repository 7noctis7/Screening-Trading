"""Canaux d'alerte (sinks) — 1 destination = 1 classe, même interface.

InMemorySink/ConsoleSink testables ; Telegram/Discord isolent le réseau et exposent un
formateur pur (`format_message`) testable. Chaque sink a un seuil de sévérité minimal.
"""

from __future__ import annotations

import json
import os
import urllib.request

from packages.alerts.models import Alert, Severity

_EMOJI = {Severity.INFO: "ℹ️", Severity.WARNING: "⚠️", Severity.CRITICAL: "🚨"}


def format_message(alert: Alert) -> str:
    """Rendu texte pur d'une alerte (testable, réutilisé par tous les canaux réseau)."""
    icon = _EMOJI.get(alert.severity, "")
    return f"{icon} [{alert.severity.name}] {alert.kind.upper()} — {alert.message}"


class InMemorySink:
    name = "memory"

    def __init__(self, min_severity: Severity = Severity.INFO) -> None:
        self.min_severity = min_severity
        self.received: list[Alert] = []

    def send(self, alert: Alert) -> None:
        self.received.append(alert)


class ConsoleSink:
    name = "console"

    def __init__(self, min_severity: Severity = Severity.INFO) -> None:
        self.min_severity = min_severity

    def send(self, alert: Alert) -> None:
        print(format_message(alert))


class TelegramSink:
    name = "telegram"

    def __init__(self, token: str | None = None, chat_id: str | None = None,
                 min_severity: Severity = Severity.WARNING) -> None:
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.min_severity = min_severity

    def send(self, alert: Alert) -> None:  # réseau (ton env)
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = json.dumps({"chat_id": self.chat_id, "text": format_message(alert)}).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)


class DiscordSink:
    name = "discord"

    def __init__(self, webhook_url: str | None = None,
                 min_severity: Severity = Severity.WARNING) -> None:
        self.webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL", "")
        self.min_severity = min_severity

    def send(self, alert: Alert) -> None:  # réseau (ton env)
        body = json.dumps({"content": format_message(alert)}).encode()
        req = urllib.request.Request(self.webhook_url, data=body,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
