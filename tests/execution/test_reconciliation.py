from packages.execution.reconciliation import reconcile, fill_rate


def test_reconcile_generates_orders():
    r = reconcile({"AAPL": 0.5, "MSFT": 0.5}, {"AAPL": 1000.0}, equity=4000.0)
    syms = {o["symbol"]: o for o in r["orders"]}
    assert syms["AAPL"]["side"] == "buy" and syms["AAPL"]["delta_usd"] == 1000.0   # 2000 cible - 1000
    assert syms["MSFT"]["side"] == "buy" and syms["MSFT"]["delta_usd"] == 2000.0
    assert r["n_orders"] == 2


def test_reconcile_sell_when_overweight():
    r = reconcile({"AAPL": 0.25}, {"AAPL": 1000.0}, equity=2000.0)   # cible 500 < 1000
    assert r["orders"][0]["side"] == "sell"


def test_fill_rate():
    assert fill_rate(10, 8)["fill_rate"] == 0.8
