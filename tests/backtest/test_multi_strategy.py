import numpy as np
from packages.backtest.multi_strategy import run_multi_strategy


def test_runs_and_has_all_strategies():
    rng = np.random.default_rng(0)
    closes = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, 400))
    r = run_multi_strategy(closes)
    assert r["available"]
    names = {s["name"] for s in r["strategies"]}
    assert len(names) == 3 and "combined" in r and r["best"] in names


def test_metrics_bounds():
    rng = np.random.default_rng(1)
    closes = 100 * np.cumprod(1 + rng.normal(0.0005, 0.012, 500))
    r = run_multi_strategy(closes)
    for s in r["strategies"] + [r["combined"]]:
        assert 0.0 <= s["exposure"] <= 1.0
        assert s["max_drawdown"] <= 0.0


def test_uptrend_trend_strategy_profits():
    closes = np.linspace(100, 200, 300)        # tendance haussière pure
    r = run_multi_strategy(closes)
    trend = next(s for s in r["strategies"] if s["name"].startswith("Tendance"))
    assert trend["total_return"] > 0


def test_too_short():
    assert run_multi_strategy([1, 2, 3])["available"] is False
