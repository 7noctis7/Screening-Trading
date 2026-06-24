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


def test_signals_for_maps_first_match():
    from packages.data.prediction_markets import signals_for
    recs = [
        {"question": "Fed rate cut in July?", "probability": 0.62},
        {"question": "CPI above 3% in June?", "probability": 0.41},
    ]
    km = {"fed": ["fed", "fomc"], "cpi": ["cpi"], "btc": ["bitcoin"]}
    out = signals_for(recs, km)
    assert out["fed"] == 0.62 and out["cpi"] == 0.41 and out["btc"] is None


def test_macro_signals_offline_injected():
    from packages.data.prediction_markets import macro_signals
    recs = [{"question": "Will the Fed cut rates?", "probability": 0.7},
            {"question": "US recession in 2026?", "probability": 0.3}]
    out = macro_signals(records=recs)
    assert out["fed_rate_cut"] == 0.7 and out["recession"] == 0.3
    assert out["cpi_inflation"] is None


def test_asset_signals_matches_ticker_and_crypto_name():
    from packages.data.prediction_markets import asset_signals
    recs = [{"question": "Will NVDA hit $2000?", "probability": 0.2},
            {"question": "Bitcoin above 100k in 2026?", "probability": 0.55}]
    out = asset_signals(["NVDA", "BTC"], records=recs)
    assert out["NVDA"] == 0.2 and out["BTC"] == 0.55


def test_earnings_signals_requires_earnings_term_and_asset():
    from packages.data.prediction_markets import earnings_signals
    recs = [{"question": "Will Apple beat earnings in Q3?", "probability": 0.6},
            {"question": "Apple new product launch?", "probability": 0.9}]
    out = earnings_signals(["AAPL"], records=recs, names={"AAPL": "Apple"})
    assert out["AAPL"] == 0.6      # le launch (0.9) est ignoré (pas un terme résultats)


def test_debias_pushes_extremes_and_keeps_half():
    from packages.data.prediction_markets import debias
    assert debias(0.5) == 0.5                 # 50 % invariant
    assert debias(0.8) > 0.8                   # favori sous-pricé → relevé
    assert debias(0.2) < 0.2                   # outsider sur-pricé → abaissé
    assert debias(0.5, alpha=1.0) == 0.5       # alpha=1 → identité


def test_polymarket_mid_from_bid_ask_and_spread():
    data = [{"question": "Fed cuts?", "bestBid": 0.60, "bestAsk": 0.66,
             "volume24hr": 1e6, "endDate": "2026-07-31"}]
    out = _parse_polymarket(data)
    assert out[0]["probability"] == 0.63       # mid = (0.60+0.66)/2
    assert out[0]["spread"] == 0.06 and out[0]["volume"] == 1e6


def test_kalshi_mid_from_bid_ask():
    data = {"markets": [{"title": "CPI hot?", "yes_bid": 40, "yes_ask": 44,
                         "volume": 5000}]}
    out = _parse_kalshi(data)
    assert out[0]["probability"] == 0.42 and out[0]["spread"] == 0.04


def test_signals_detail_filters_illiquid_and_debiases():
    from packages.data.prediction_markets import signals_detail
    recs = [
        {"question": "Fed rate cut?", "probability": 0.8, "spread": 0.02,
         "source": "kalshi", "volume": 1000},
        {"question": "Recession soon?", "probability": 0.3, "spread": 0.40,  # illiquide
         "source": "polymarket", "volume": 10},
    ]
    out = signals_detail(recs, {"fed": ["fed"], "rec": ["recession"]})
    assert out["fed"]["p"] == 0.8 and out["fed"]["p_adj"] > 0.8   # dé-biaisé
    assert out["rec"] is None                              # spread>15 % → ignoré


def test_macro_and_earnings_detail_shapes():
    from packages.data.prediction_markets import earnings_detail, macro_detail
    recs = [{"question": "Will the Fed cut rates?", "probability": 0.7, "spread": 0.03},
            {"question": "Will Apple beat earnings?", "probability": 0.6,
             "spread": 0.05}]
    macro = macro_detail(records=recs)
    assert macro["fed_rate_cut"]["p"] == 0.7 and "p_adj" in macro["fed_rate_cut"]
    earn = earnings_detail(["AAPL"], records=recs, names={"AAPL": "Apple"})
    assert earn["AAPL"]["p"] == 0.6 and earn["AAPL"]["p_adj"] != 0.6
