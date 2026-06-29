"""Tests text-to-filter déterministe (hors-ligne)."""

from packages.research.crypto_query import _amount, apply_filter, parse_query


def test_amount_units():
    assert _amount("1 milliard") == 1e9
    assert _amount("1,5 milliard") == 1.5e9
    assert _amount("500 millions") == 5e8
    assert _amount("10md") == 1e10
    assert _amount("2B") == 2e9


def test_parse_query_clauses():
    p = parse_query("cryptos avec funding négatif et cap > 1 milliard")
    assert p["funding_max"] == 0.0 and p["mcap_min"] == 1e9
    p2 = parse_query("gagnants hausse > 5% top 10")
    assert p2["chg24h_min"] == 5.0 and p2["limit"] == 10
    p3 = parse_query("perdants baisse > 8%")
    assert p3["chg24h_max"] == -8.0


def test_apply_filter_deterministic():
    rows = [
        {"sym": "BTC", "mcap": 1.2e12, "chg24h": 1.0, "funding": -0.0001},
        {"sym": "X", "mcap": 5e8, "chg24h": 9.0, "funding": 0.001},
        {"sym": "ETH", "mcap": 4e11, "chg24h": -2.0, "funding": -0.0002},
    ]
    p = parse_query("funding négatif et cap > 1 milliard")
    out = apply_filter(rows, p)
    assert [r["sym"] for r in out] == ["BTC", "ETH"]      # X exclu (cap < 1Md, funding +)
    top1 = apply_filter(rows, {"limit": 1})
    assert top1[0]["sym"] == "BTC"                        # trié par cap desc


def test_empty_query_returns_all_sorted():
    rows = [{"sym": "A", "mcap": 1}, {"sym": "B", "mcap": 2}]
    assert [r["sym"] for r in apply_filter(rows, parse_query("bonjour"))] == ["B", "A"]
