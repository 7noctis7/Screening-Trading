from packages.data.universe import constituent_sources

FIX = "tests/universe/fixtures/ishares_holdings.csv"


def test_ishares_parses_equity_only_and_dot_to_dash():
    src = constituent_sources.create("ishares_holdings", id="iwb", url="x")
    inst = src.parse(open(FIX, encoding="utf-8").read())
    syms = [i.symbol for i in inst]
    assert syms == ["AAPL", "MSFT", "BRK-B"]   # cash exclu, BRK.B -> BRK-B
    assert src.requires_network is True
