from types import SimpleNamespace
from packages.portfolio.capacity import turnover, capacity_estimate
from packages.portfolio.rebalance import apply_no_trade_band


def _t(qty, e, x):
    return SimpleNamespace(qty=qty, entry_price=e, exit_price=x)


def test_turnover_annualized():
    trades = [_t(10, 100, 110), _t(5, 50, 55)]
    r = turnover(trades, avg_equity=10000, period_days=252)
    assert r["n_round_trips"] == 2 and r["annualized"] > 0


def test_turnover_empty():
    assert turnover([], 1000, 252)["annualized"] == 0.0


def test_capacity():
    c = capacity_estimate(1_000_000, participation=0.1)
    assert c["max_position_usd"] == 100000.0


def test_no_trade_band_filters_small():
    r = apply_no_trade_band({"A": 0.30, "B": 0.205}, {"A": 0.10, "B": 0.20}, band=0.02)
    syms = {o["symbol"] for o in r["orders"]}
    assert "A" in syms and "B" not in syms and r["filtered"] == 1


def test_no_trade_band_exit():
    r = apply_no_trade_band({"A": 0.5}, {"A": 0.4, "B": 0.1}, band=0.02)
    assert any(o["symbol"] == "B" and o["target"] == 0.0 for o in r["orders"])
