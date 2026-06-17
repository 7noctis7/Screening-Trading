import numpy as np
from types import SimpleNamespace
from packages.backtest.weighting_backtest import weighting_backtest


def _bars(c):
    return [SimpleNamespace(close=float(x)) for x in c]


def test_runs_all_schemes():
    rng = np.random.default_rng(0)
    data = {f"S{i}": _bars(100 * np.cumprod(1 + rng.normal(0.0004, 0.015 + i * 0.001, 500)))
            for i in range(14)}
    r = weighting_backtest(data, step=21, lookback_cov=126, max_assets=14)
    assert r["available"]
    assert set(r["schemes"]) == {"Équipondéré", "Inverse-vol", "Variance-min", "Risk-parity (ERC)"}
    for m in r["schemes"].values():
        assert m["available"] and m["max_drawdown"] <= 0


def test_band_reduces_turnover():
    rng = np.random.default_rng(1)
    data = {f"S{i}": _bars(100 * np.cumprod(1 + rng.normal(0.0003, 0.02, 500))) for i in range(12)}
    a = weighting_backtest(data, band=0.0, max_assets=12)
    b = weighting_backtest(data, band=0.05, max_assets=12)
    assert b["schemes"]["Inverse-vol"]["turnover_annual"] <= a["schemes"]["Inverse-vol"]["turnover_annual"]
