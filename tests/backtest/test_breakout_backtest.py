from types import SimpleNamespace
from packages.backtest.breakout_backtest import breakout_backtest


def _bars(prices):
    return [SimpleNamespace(open=p, high=p, low=p, close=p) for p in prices]


def test_detects_breakouts_and_metrics():
    # cycles plateau -> cassure repetes => beaucoup d'evenements
    data = {}
    for k in range(30):
        seq = []
        lvl = 100.0
        for _c in range(6):
            seq += [lvl] * 24
            seq += [lvl + i for i in range(1, 30)]   # rampe = cassure
            lvl = seq[-1]
        data[f"S{k}"] = _bars(seq)
    r = breakout_backtest(data, lookback=20, hold=21)
    assert r["available"] and r["n_events"] >= 20
    assert 0 <= r["win_rate"] <= 1 and "t_stat" in r and "edge_vs_market" in r


def test_too_short():
    assert breakout_backtest({"A": _bars(range(1, 30))}, lookback=20, hold=21)["available"] is False
