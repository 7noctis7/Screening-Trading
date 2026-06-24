"""Tests connecteur prediction-markets (parsing hors-ligne, sans réseau)."""

from packages.data.prediction_markets import (
    _parse_kalshi,
    _parse_polymarket,
    fetch_markets,
    implied_probability,
)


def test_parse_polymarket():
    data = [
        {"question": "Fed cuts in July?", "outcomePrices": "[\"0.62\", \"0.38\"]",
         "endDate": "2026-07-31"},
        {"title": "no price here"},                      # ignoré (pas de prix)
    ]
    out = _parse_polymarket(data)
    assert len(out) == 1
    assert out[0]["source"] == "polymarket" and out[0]["probability"] == 0.62


def test_parse_kalshi_cents_to_prob():
    data = {"markets": [
        {"title": "CPI above 3%?", "last_price": 41, "close_time": "2026-07-10"},
        {"ticker": "X", "yes_bid": 75},
    ]}
    out = _parse_kalshi(data)
    assert out[0]["probability"] == 0.41 and out[0]["source"] == "kalshi"
    assert out[1]["probability"] == 0.75


def test_parse_handles_empty_or_garbage():
    assert _parse_polymarket(None) == []
    assert _parse_kalshi({}) == []
    assert _parse_polymarket([{"question": "x", "outcomePrices": "not json"}]) == []


def test_implied_probability_keyword():
    recs = [{"question": "Fed rate cut in July?", "probability": 0.62},
            {"question": "Recession in 2026?", "probability": 0.30}]
    assert implied_probability(recs, "fed") == 0.62
    assert implied_probability(recs, "recession") == 0.30
    assert implied_probability(recs, "bitcoin") is None


def test_fetch_markets_offline_safe():
    # sans réseau (ou si bloqué), fetch_markets ne doit jamais lever — renvoie une liste
    assert isinstance(fetch_markets(limit=1), list)
