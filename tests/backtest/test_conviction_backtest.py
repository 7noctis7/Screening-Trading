import numpy as np
from types import SimpleNamespace
from packages.backtest.conviction_backtest import conviction_backtest


def _bars(closes):
    return [SimpleNamespace(close=float(c)) for c in closes]


def test_runs_and_compares():
    rng = np.random.default_rng(0)
    data = {}
    for i in range(20):
        drift = 0.0005 + i * 0.00003
        data[f"S{i}"] = _bars(100 * np.cumprod(1 + rng.normal(drift, 0.02, 400)))
    r = conviction_backtest(data, step=21, top_n=8)
    assert r["available"]
    for k in ("strategy", "benchmark"):
        assert r[k]["available"] and r[k]["max_drawdown"] <= 0
    assert "alpha" in r and r["turnover_annual"] >= 0


def test_too_few_assets():
    assert conviction_backtest({"A": _bars(range(1, 300))})["available"] is False
