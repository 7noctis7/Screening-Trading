"""Tests connecteur funding crypto (parsing hors-ligne, sans réseau)."""

from packages.data.funding import (
    _parse_binance,
    _parse_bybit,
    daily_funding,
    fetch_funding,
)


def test_parse_binance_sorts_and_casts():
    data = [{"fundingTime": 200, "fundingRate": "0.0003"},
            {"fundingTime": 100, "fundingRate": "-0.0001"},
            {"bad": "row"}]
    out = _parse_binance(data)
    assert len(out) == 2 and out[0]["ts_ms"] == 100        # trié croissant
    assert out[1]["rate"] == 0.0003


def test_parse_bybit_shape():
    data = {"result": {"list": [
        {"fundingRateTimestamp": "1700000000000", "fundingRate": "0.0005"}]}}
    out = _parse_bybit(data)
    assert out[0]["rate"] == 0.0005 and out[0]["ts_ms"] == 1700000000000


def test_parse_empty_safe():
    assert _parse_binance(None) == [] and _parse_bybit({}) == []


def test_daily_funding_aggregates_per_day():
    # 3 fundings le même jour (8h) → somme ; jour suivant séparé.
    day0 = 1_699_920_000_000          # ms = 2023-11-14 00:00 UTC (minuit)
    recs = [{"ts_ms": day0, "rate": 0.0001},
            {"ts_ms": day0 + 8 * 3600_000, "rate": 0.0001},
            {"ts_ms": day0 + 16 * 3600_000, "rate": 0.0001},
            {"ts_ms": day0 + 26 * 3600_000, "rate": 0.0009}]
    d = daily_funding(recs)
    vals = sorted(d.values())
    assert len(d) == 2
    assert abs(vals[0] - 0.0003) < 1e-9 and abs(vals[1] - 0.0009) < 1e-9


def test_fetch_offline_safe():
    assert isinstance(fetch_funding("BTC", limit=1), list)
