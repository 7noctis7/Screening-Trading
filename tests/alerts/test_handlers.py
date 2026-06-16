from packages.common.event_bus import EventBus, Topic
from packages.alerts import AlertEngine, InMemorySink, Severity, register_on_bus
from packages.alerts import handlers as H


def test_kill_switch_is_critical():
    a = H.on_kill_switch({"drawdown": "-6%"})
    assert a.severity is Severity.CRITICAL and a.kind == "risk"


def test_regime_riskoff_is_warning():
    assert H.on_regime_changed({"to": "risk_off"}).severity is Severity.WARNING
    assert H.on_regime_changed({"to": "expansion"}).severity is Severity.INFO


def test_bus_wiring_routes_to_engine():
    bus = EventBus(); mem = InMemorySink()
    register_on_bus(AlertEngine([mem]), bus)
    bus.publish(Topic.KILL_SWITCH, {"drawdown": "-5%"})
    bus.publish(Topic.DATA_QUALITY_FAILED, {"symbol": "AAPL", "detail": "gap"})
    kinds = {a.kind for a in mem.received}
    assert {"risk", "data"} <= kinds
