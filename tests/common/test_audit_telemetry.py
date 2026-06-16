from packages.common.audit import AuditTrail
from packages.common.telemetry import Metrics


def test_audit_records_and_replays_in_order():
    a = AuditTrail(":memory:")
    a.record("order", {"sym": "AAPL"})
    a.record("regime", {"to": "risk_off"})
    seq = list(a.replay())
    assert [e["kind"] for e in seq] == ["order", "regime"]
    assert a.query("order")[0]["context"]["sym"] == "AAPL"


def test_telemetry_snapshot():
    m = Metrics()
    m.incr("orders", 3)
    m.gauge("equity", 100_000)
    with m.timer("step"):
        pass
    snap = m.snapshot()
    assert snap["counters"]["orders"] == 3
    assert snap["gauges"]["equity"] == 100_000
    assert snap["timers"]["step"]["count"] == 1
