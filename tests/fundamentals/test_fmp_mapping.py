"""Pipeline FMP réel — mapping pur JSON→Financials testé hors-ligne (sans réseau ni clé)."""
from packages.fundamentals.fmp_provider import build_financials
from packages.fundamentals import valuation, ratios
from packages.fundamentals.scoring import altman_z


def _fixtures():
    income = {"date": "2024-12-31", "revenue": 1000.0, "grossProfit": 600.0,
              "operatingIncome": 250.0, "ebitda": 300.0, "netIncome": 200.0,
              "interestExpense": 5.0, "weightedAverageShsOutDil": 100.0}
    balance = {"date": "2024-12-31", "totalStockholdersEquity": 800.0,
               "totalDebt": 100.0, "cashAndCashEquivalents": 150.0}
    cashflow = {"freeCashFlow": 220.0}
    profile = {"price": 50.0, "sector": "Technology", "mktCap": 5000.0}
    return income, balance, cashflow, profile


def test_build_financials_maps_fields():
    f = build_financials("AAPL", *_fixtures())
    assert f.symbol == "AAPL" and f.sector == "Technology"
    assert f.revenue == 1000.0 and f.net_income == 200.0 and f.shares == 100.0
    assert f.price == 50.0 and f.as_of.year == 2024


def test_downstream_metrics_work_on_fmp_data():
    f = build_financials("AAPL", *_fixtures())
    assert valuation.per(f) > 0            # PER calculable
    assert ratios.roe(f) > 0
    assert altman_z(f)["zone"] in ("sûr", "gris", "détresse")


def test_shares_fallback_from_mktcap():
    income, balance, cashflow, profile = _fixtures()
    income["weightedAverageShsOutDil"] = 0      # force le repli mktCap/price
    f = build_financials("X", income, balance, cashflow, profile)
    assert f.shares == 100.0                      # 5000 / 50
