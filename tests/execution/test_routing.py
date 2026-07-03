"""Routage des tickers vers les brokers (ère paper = mono-broker Alpaca ; crypto /USD)."""

from packages.execution.routing import is_tradeable, route


def test_us_equity_alpaca():
    r = route("AAPL", "equity")
    assert r["broker"] == "Alpaca" and r["tradeable"] and r["broker_symbol"] == "AAPL"


def test_foreign_not_tradeable_on_alpaca():
    for sym in ("AKZA.AS", "SU.PA", "DSFIR.AS", "BMW.DE"):
        assert is_tradeable(sym, "equity") is False


def test_crypto_whitelisted_routes_to_alpaca_usd():
    # ère paper : la crypto supportée par Alpaca est négociable en paires /USD.
    r = route("BTC/USDC", "crypto")
    assert r["broker"] == "Alpaca" and r["tradeable"]
    assert r["broker_symbol"] == "BTC/USD"
    assert route("ETH/USDC", "crypto")["broker_symbol"] == "ETH/USD"
    assert route("BTC-USD", "crypto")["broker_symbol"] == "BTC/USD"


def test_crypto_not_whitelisted_excluded_never_bitmart():
    # base hors whitelist Alpaca → exclue de l'univers papier, JAMAIS routée vers Bitmart.
    r = route("HYPE/USDC", "crypto")
    assert r["broker"] != "Bitmart"          # Bitmart reste OFF / futur-live gated
    assert r["tradeable"] is False
    assert "whitelist" in r["reason"].lower()


def test_unsupported_class_not_tradeable():
    assert is_tradeable("GC=F", "commodity") is False     # commodité : pas de broker spot
