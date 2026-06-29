"""Tests dérivés crypto — adaptateurs/normaliseurs purs (hors-ligne)."""

from packages.data.deriv_normalizer import (
    Liq,
    aggregate_funding,
    from_binance_premium,
    from_bybit_ticker,
    from_okx,
    funding_sentiment,
    liq_from_binance,
    liquidation_sentiment,
)


def test_funding_adapters_heterogeneous():
    assert from_bybit_ticker({"result": {"list": [{"fundingRate": "0.0001"}]}}) == 0.0001
    assert from_okx({"data": [{"fundingRate": "0.0002"}]}) == 0.0002
    assert from_binance_premium({"lastFundingRate": "0.00015"}) == 0.00015
    assert from_bybit_ticker({}) is None and from_okx(None) is None


def test_aggregate_funding_mean_and_annualized():
    agg = aggregate_funding({"bybit": 0.0001, "okx": 0.0003, "binance": None})
    assert agg["available"] and agg["n_venues"] == 2
    assert agg["mean"] == 0.0002
    assert round(agg["annualized"], 4) == round(0.0002 * 3 * 365, 4)
    assert aggregate_funding({"bybit": None})["available"] is False


def test_funding_sentiment_labels():
    hot = funding_sentiment([{"available": True, "mean": 0.001}])
    assert "longs surchauffés" in hot["label"]
    cold = funding_sentiment([{"available": True, "mean": -0.001}])
    assert "shorts surchauffés" in cold["label"]
    flat = funding_sentiment([{"available": True, "mean": 0.0}])
    assert "équilibré" in flat["label"]
    assert funding_sentiment([])["available"] is False


def test_liquidation_normalize_and_sentiment():
    raw = {"o": {"T": 1, "s": "BTCUSDT", "S": "SELL", "q": "2", "ap": "50000"}}
    e = liq_from_binance(raw)
    assert e.exchange == "binance" and e.side == "long" and e.usd == 100000.0
    out = liquidation_sentiment([
        e,                                                   # 100k longs liquidés
        Liq(2, "bybit", "BTCUSDT", "short", 10000.0),        # 10k shorts liquidés
    ])
    assert out["available"] and out["score"] < -0.33        # longs balayés → capitulation
    assert "capitulation" in out["label"]
    assert liquidation_sentiment([])["available"] is False
