from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from packages.storage.data_health import series_health, health_report


def _bars(n, last_days_ago=0, bad=0):
    now = datetime.now(timezone.utc)
    out = []
    for i in range(n):
        c = 100.0 + i
        out.append(SimpleNamespace(close=c, ts=now - timedelta(days=(n - i + last_days_ago))))
    for i in range(bad):
        out[i] = SimpleNamespace(close=0.0, ts=out[i].ts)
    return out


def test_series_complete():
    h = series_health("A", _bars(300))
    assert h["complete"] and h["n_bars"] == 300 and h["n_bad"] == 0


def test_series_short_incomplete():
    h = series_health("B", _bars(100))
    assert not h["complete"]


def test_report_score_and_coverage():
    data = {"A": _bars(300), "B": _bars(300), "C": _bars(100, bad=2)}
    acmap = {"A": "equity", "B": "equity", "C": "crypto"}
    rep = health_report(data, acmap)
    assert 0 <= rep["score"] <= 100 and rep["n_series"] == 3
    classes = {c["asset_class"] for c in rep["coverage"]}
    assert classes == {"equity", "crypto"}
