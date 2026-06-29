"""Tests historiques crypto — parsers purs (hors-ligne)."""

from packages.data.crypto_history import (
    align,
    parse_fng_history,
    parse_market_chart,
    parse_tvl_history,
)


def test_parse_fng_history_sorted_deduped():
    # 1517463000 = 2018-02-01, 1517549400 = 2018-02-02 ; doublon jour → dernier gardé
    out = parse_fng_history({"data": [
        {"timestamp": "1517549400", "value": "60"},
        {"timestamp": "1517463000", "value": "30"},
        {"timestamp": "1517463000", "value": "40"},
        {"timestamp": "bad", "value": "x"},
    ]})
    assert out == [("2018-02-01", 40.0), ("2018-02-02", 60.0)]


def test_parse_market_chart():
    out = parse_market_chart({"prices": [
        [1517443200000, 9000.0], [1517529600000, 9100.0], [1517529600000, 9150.0],
        ["bad", 1], [123],
    ]})
    assert out[0][1] == 9000.0 and out[-1] == ("2018-02-02", 9150.0)


def test_parse_tvl_history():
    out = parse_tvl_history([{"date": 1517443200, "tvl": 1e9},
                             {"date": 1517529600, "tvl": 1.1e9},
                             {"date": None, "tvl": 5}])
    assert len(out) == 2 and out[0][1] == 1e9


def test_align_inner_join():
    a = [("d1", 1.0), ("d2", 2.0), ("d3", 3.0)]
    b = [("d2", 20.0), ("d3", 30.0), ("d4", 40.0)]
    dates, va, vb = align(a, b)
    assert dates == ["d2", "d3"] and va == [2.0, 3.0] and vb == [20.0, 30.0]


def test_parsers_empty_safe():
    assert parse_fng_history(None) == []
    assert parse_market_chart({}) == []
    assert parse_tvl_history(None) == []
