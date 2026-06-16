from packages.fundamentals import build_financials, ratios, valuation


def test_build_financials_maps_fields():
    income = {"date": "2024-12-31", "revenue": 1000, "grossProfit": 400,
              "operatingIncome": 200, "ebitda": 250, "netIncome": 150,
              "interestExpense": 12, "weightedAverageShsOut": 1000}
    balance = {"date": "2024-12-31", "totalStockholdersEquity": 500,
               "totalDebt": 300, "cashAndCashEquivalents": 100}
    cashflow = {"freeCashFlow": 120}
    profile = {"price": 100, "sector": "Technology", "mktCap": 100000}
    f = build_financials("AAPL", income, balance, cashflow, profile)
    assert f.symbol == "AAPL" and f.sector == "Technology"
    assert f.revenue == 1000 and f.net_income == 150 and f.fcf == 120
    assert abs(ratios.roe(f) - 0.30) < 1e-9
    assert abs(valuation.ev_ebitda(f) - (100000 + 300 - 100) / 250) < 1e-6


def test_build_financials_defensive_on_missing():
    f = build_financials("X", {}, {}, {}, {"price": 50})
    assert f.price == 50.0 and f.revenue == 0.0  # pas d'exception
