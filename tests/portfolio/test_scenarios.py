from packages.portfolio.scenarios import scenario_analysis, hedge_suggestion, SCENARIOS


def test_scenarios_sorted_worst_first():
    res = scenario_analysis({"equity": 1.0})
    assert res[0]["pnl_pct"] <= res[-1]["pnl_pct"]
    assert any(s["name"].startswith("Krach") for s in res)


def test_full_equity_2008_matches_shock():
    res = scenario_analysis({"equity": 1.0})
    krach = next(s for s in res if s["name"].startswith("Krach"))
    assert abs(krach["pnl_pct"] - SCENARIOS["Krach actions (type 2008)"]["equity"]) < 1e-9


def test_hedge_needed_when_breaching_target():
    h = hedge_suggestion({"equity": 1.0}, target_max_loss=-0.15)
    assert h["needed"] and h["hedge_pct"] > 0 and h["worst_pnl_pct"] < -0.15


def test_no_hedge_when_within_target():
    h = hedge_suggestion({"forex": 1.0}, target_max_loss=-0.15)
    assert not h["needed"] and h["hedge_pct"] == 0.0


def test_empty_portfolio():
    assert scenario_analysis({}) [0]["pnl_pct"] == 0.0
