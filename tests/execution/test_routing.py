"""Routage des tickers vers les brokers (Alpaca US / Bitmart crypto)."""

from packages.execution.routing import is_tradeable, route


def test_us_equity_alpaca():
    r = route("AAPL", "equity")
    assert r["broker"] == "Alpaca" and r["tradeable"] and r["broker_symbol"] == "AAPL"


def test_foreign_not_tradeable_on_alpaca():
    for sym in ("AKZA.AS", "SU.PA", "DSFIR.AS", "BMW.DE"):
        assert is_tradeable(sym, "equity") is False


def test_crypto_routes_to_bitmart_usdt():
    r = route("IOTA/USDC", "crypto")
    assert r["broker"] == "Bitmart" and r["tradeable"]
    assert r["broker_symbol"] == "IOTA/USDT"
    assert route("BTC-USD", "crypto")["broker_symbol"] == "BTC/USDT"


def test_unsupported_class_not_tradeable():
    assert is_tradeable("GC=F", "commodity") is False     # commodité : pas de broker spot
