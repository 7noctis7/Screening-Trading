"""Câblage AlertEngine ↔ event bus en prod : une divergence / un fill partiel inconnu
doit produire une alerte CRITICAL réelle (via InMemorySink), sans dépendre des demos.
"""
from __future__ import annotations

import pytest

from packages.alerts import AlertEngine, InMemorySink, Severity
from packages.alerts.wiring import attach_to_bus, default_engine
from packages.common.event_bus import EventBus, Topic
from packages.core.models import Position, Side
from packages.execution.reconcile import reconcile


def test_reconcile_divergence_emits_critical_alert():
    bus = EventBus()
    sink = InMemorySink()
    attach_to_bus(bus, AlertEngine([sink]))
    # broker détient 2 AAPL, l'interne 0 → divergence.
    reconcile([Position("AAPL", Side.LONG, 2.0, 100.0)], [], bus=bus)
    assert len(sink.received) == 1
    assert sink.received[0].severity is Severity.CRITICAL
    assert sink.received[0].kind == "execution"
    assert "AAPL" in str(sink.received[0].data)


def test_reconcile_no_divergence_no_alert():
    bus = EventBus()
    sink = InMemorySink()
    attach_to_bus(bus, AlertEngine([sink]))
    pos = [Position("AAPL", Side.LONG, 2.0, 100.0)]
    reconcile(pos, pos, bus=bus)
    assert sink.received == []


def test_partial_fill_unknown_emits_critical_alert():
    bus = EventBus()
    sink = InMemorySink()
    attach_to_bus(bus, AlertEngine([sink]))
    bus.publish(Topic.PARTIAL_FILL_UNKNOWN, {"symbol": "BTC/USDT", "requested": 0.5})
    assert len(sink.received) == 1
    assert sink.received[0].severity is Severity.CRITICAL
    assert "BTC/USDT" in sink.received[0].message


def test_default_engine_console_only_without_keys(monkeypatch):
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "DISCORD_WEBHOOK_URL"):
        monkeypatch.delenv(k, raising=False)
    eng = default_engine()
    assert [s.name for s in eng.sinks] == ["console"]


def test_default_engine_adds_channels_when_keys_present(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/wh")
    eng = default_engine()
    names = {s.name for s in eng.sinks}
    assert names == {"console", "telegram", "discord"}
