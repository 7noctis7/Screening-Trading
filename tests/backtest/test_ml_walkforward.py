import numpy as np
from types import SimpleNamespace
from packages.backtest.ml_walkforward import ml_walkforward


def _bars(closes):
    return [SimpleNamespace(close=float(c)) for c in closes]


def test_walkforward_runs_and_compares():
    rng = np.random.default_rng(0)
    data = {f"S{i}": _bars(100 * np.cumprod(1 + rng.normal(0.0004 + i * 0.00002, 0.02, 360)))
            for i in range(16)}
    r = ml_walkforward(data, step=21, max_assets=16, max_train=2000)
    assert r["available"]
    for k in ("ml", "tech", "benchmark"):
        assert r[k]["available"] and r[k]["max_drawdown"] <= 0
        assert 0.0 <= r[k]["dsr"] <= 1.0


def test_too_few_assets():
    assert ml_walkforward({"A": _bars(range(1, 300))})["available"] is False
