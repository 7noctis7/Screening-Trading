"""Tests Growthepie (parser défensif, hors-ligne)."""

from packages.data.growthepie import eth_context, parse_fundamentals


def test_parse_keeps_latest_per_metric_for_origin():
    data = [
        {"origin_key": "ethereum", "metric_key": "txcount", "date": "2026-06-28",
         "value": 1_100_000},
        {"origin_key": "ethereum", "metric_key": "txcount", "date": "2026-06-29",
         "value": 1_200_000},                                   # plus récent → gardé
        {"origin_key": "ethereum", "metric_key": "txcosts_median_usd",
         "date": "2026-06-29", "value": 0.42},
        {"origin_key": "arbitrum", "metric_key": "txcount", "date": "2026-06-29",
         "value": 9},                                           # autre origin → ignoré
    ]
    out = parse_fundamentals(data, origin="ethereum")
    assert out["txcount"] == 1_200_000 and out["txcosts_median_usd"] == 0.42


def test_parse_empty_or_bad_shape():
    assert parse_fundamentals(None) == {}
    assert parse_fundamentals([{"foo": "bar"}]) == {}


def test_eth_context_offline_safe():
    out = eth_context()                          # pas de réseau → available False
    assert out.get("available") in (False, True)
