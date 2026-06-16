from packages.alerts import AlertEngine, InMemorySink, Severity, Throttle, format_message
from packages.alerts.models import Alert


def _alert(sev, key="k"):
    return Alert("risk", sev, "msg", dedup_key=key)


def test_severity_routing():
    low = InMemorySink(min_severity=Severity.INFO)
    high = InMemorySink(min_severity=Severity.CRITICAL)
    eng = AlertEngine([low, high])
    eng.emit(_alert(Severity.WARNING, "w"))
    eng.emit(_alert(Severity.CRITICAL, "c"))
    assert len(low.received) == 2        # INFO sink reçoit tout
    assert len(high.received) == 1       # CRITICAL sink ne reçoit que le critique


def test_throttle_blocks_duplicate():
    mem = InMemorySink()
    eng = AlertEngine([mem], throttle=Throttle(ttl_s=1e9, clock=lambda: 0.0))
    assert eng.emit(_alert(Severity.WARNING, "dup")) is True
    assert eng.emit(_alert(Severity.WARNING, "dup")) is False
    assert len(mem.received) == 1


def test_failing_sink_does_not_break_others():
    class Bad:
        name = "bad"; min_severity = Severity.INFO
        def send(self, a): raise RuntimeError("down")
    mem = InMemorySink()
    eng = AlertEngine([Bad(), mem])
    eng.emit(_alert(Severity.CRITICAL, "x"))
    assert len(mem.received) == 1        # le canal HS n'empêche pas les autres


def test_format_message_has_severity_and_kind():
    msg = format_message(_alert(Severity.CRITICAL))
    assert "CRITICAL" in msg and "RISK" in msg
