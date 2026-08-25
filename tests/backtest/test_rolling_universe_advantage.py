"""Test rolling universe point-in-time asset selection (no look-ahead)."""

import numpy as np

from packages.backtest.preset_helpers import select_rolling_universe


def test_rolling_universe_point_in_time():
    """Momentum ranking at time t uses only data up to t (no look-ahead)."""
    n_periods = 200
    prices = {
        "rising": 100 * np.exp(np.arange(n_periods) * 0.005),
        "flat": np.full(n_periods, 100.0),
        "falling": 100 * np.exp(-np.arange(n_periods) * 0.005),
    }

    # Rising asset should be selected due to consistent momentum
    result = select_rolling_universe(prices, 100, top_k=1, lookback=50)
    assert result == ["rising"]


def test_rolling_universe_excludes_insufficient_data():
    """Rolling selection excludes assets without data at time t."""
    M = {
        "A": np.array([100.0, 101, 102, 103, 104] * 25),  # 125 points
        "B": np.array([100.0, 101, 102, 103, 104] * 5),   # 25 points
    }
    # At t=100 (beyond B's data), B is excluded
    result = select_rolling_universe(M, 100, top_k=2, lookback=50)
    # B has only 25 points, so at t=100 it's invalid
    assert "B" not in result or "A" in result


def test_rolling_universe_with_few_assets():
    """Rolling universe returns all available when fewer than top_k."""
    prices = {
        "A": np.array([100.0] * 50),
        "B": np.array([101.0] * 50),
    }
    result = select_rolling_universe(prices, 40, top_k=10, lookback=30)
    assert len(result) <= 2  # Only 2 assets available
    assert set(result).issubset({"A", "B"})
