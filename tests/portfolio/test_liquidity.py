from packages.portfolio.liquidity import liquidation_days, portfolio_liquidity, liquidity_adjusted_var


def test_liquidation_days():
    assert liquidation_days(1000, adv_usd=10000, participation=0.1) == 1.0
    assert liquidation_days(1000, adv_usd=0) == float("inf")


def test_portfolio_liquidity_flags_illiquid():
    pos = [{"symbol": "LIQ", "value": 1000, "adv": 1_000_000},
           {"symbol": "ILL", "value": 1000, "adv": 1000}]    # ILL: 10 j > 5
    r = portfolio_liquidity(pos, participation=0.1, illiquid_days=5)
    assert r["available"] and r["illiquid_pct"] == 0.5
    assert r["worst"][0]["symbol"] == "ILL"


def test_liquidity_adjusted_var_adds_cost():
    assert liquidity_adjusted_var(0.05, half_spread=0.001, days=4) == round(0.05 + 0.001 * 2, 6)
