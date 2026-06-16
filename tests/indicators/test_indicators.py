import numpy as np
from tests._helpers import mkbars
from packages.indicators import indicators


def test_sma_exact():
    out = indicators.create("sma", period=3).compute(mkbars([1, 2, 3, 4, 5]))
    assert np.isnan(out[0]) and np.isnan(out[1])
    assert out[2:] == [2.0, 3.0, 4.0]


def test_rsi_bounded():
    prices = list(100 + np.cumsum(np.random.default_rng(0).normal(0, 1, 60)))
    rsi = indicators.create("rsi", period=14).compute(mkbars(prices))
    assert all(0 <= v <= 100 for v in rsi if v == v)


def test_no_lookahead_ema():
    prices = list(100 + np.cumsum(np.random.default_rng(1).normal(0, 1, 40)))
    full = indicators.create("ema", period=10).compute(mkbars(prices))
    for i in range(12, 40):
        trunc = indicators.create("ema", period=10).compute(mkbars(prices[: i + 1]))
        assert abs(trunc[i] - full[i]) < 1e-9


def test_atr_positive():
    prices = list(100 + np.cumsum(np.random.default_rng(2).normal(0, 1, 50)))
    atr = indicators.create("atr", period=14).compute(mkbars(prices))
    assert all(v > 0 for v in atr if v == v)
