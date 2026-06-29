"""Tests du générateur de rapport crypto (déterministe, hors-ligne)."""

from packages.research.crypto_report import generate, sentiment

_BEAR = {
    "BTC": {"dd_ath": -0.53, "mom_30d": -0.19, "turnover": 0.026, "float_ratio": 0.95},
    "ETH": {"dd_ath": -0.68, "mom_30d": -0.22, "turnover": 0.057, "float_ratio": 1.0,
            "tvl_mcap": 0.196},
    "HYPE": {"dd_ath": -0.15, "mom_30d": -0.03, "turnover": 0.038, "float_ratio": 0.22},
    "ONDO": {"dd_ath": -0.85, "mom_30d": -0.09, "turnover": 0.039, "float_ratio": 0.49,
             "tvl_mcap": 2.33},
}


def test_sentiment_bearish_when_momentum_and_dd_negative():
    assert sentiment(_BEAR) == "BEARISH"


def test_sentiment_bullish_and_neutral():
    bull = {"A": {"mom_30d": 0.10, "dd_ath": -0.2}, "B": {"mom_30d": 0.08}}
    flat = {"A": {"mom_30d": 0.0, "dd_ath": -0.2}, "B": {"mom_30d": 0.01}}
    assert sentiment(bull) == "BULLISH" and sentiment(flat) == "NEUTRE"


def test_generate_is_data_driven():
    r = generate(_BEAR)
    assert r["available"] and r["sentiment"] == "BEARISH"
    blob = " ".join([r["flash"], *r["decryptage"], *r["hasheur"], *r["vigilance"]])
    assert "HYPE" in blob                      # plus bas float → cité (unlocks)
    assert "ONDO" in blob                      # RWA cité
    assert "%" in r["flash"]                    # chiffres réels, pas du vide


def test_generate_guards_small_input():
    assert generate({})["available"] is False
    assert generate({"X": {"mom_30d": -0.1}})["available"] is False  # <2 actifs


def test_eth_context_attached_when_available():
    r = generate(_BEAR, {"available": True, "tps": 14.2, "median_fee_usd": 0.42})
    assert r["eth_context"]["tps"] == 14.2
