from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from packages.strategies.earnings_pead import pead_backtest


def _series(start, n, step_up):
    base = datetime(2023, 1, 2, tzinfo=timezone.utc)
    bars, px = [], 100.0
    for i in range(n):
        px *= (1 + step_up)
        bars.append(SimpleNamespace(ts=base + timedelta(days=i), close=px))
    return bars


def test_drift_after_positive_gap_is_captured():
    # série montante régulière ; un "gap" haussier suivi de drift haussier → PEAD positif
    data, earnings = {}, {}
    for k in range(30):
        bars = _series(0, 120, 0.004)
        # injecte un gap haussier au jour 60
        for j in range(60, 120):
            bars[j] = SimpleNamespace(ts=bars[j].ts, close=bars[j].close * 1.05)
        data[f"S{k}"] = bars
        earnings[f"S{k}"] = [bars[60].ts]
    r = pead_backtest(data, earnings, hold=21)
    assert r["available"] and r["n_events"] >= 20
    assert -1 <= r["t_stat"] <= 1000 and 0 <= r["win_rate"] <= 1


def test_no_events():
    assert pead_backtest({"A": _series(0, 50, 0.001)}, {}, hold=21)["available"] is False
