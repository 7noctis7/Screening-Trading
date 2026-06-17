"""Alias Yahoo — couverture crypto/forex/indices/commodités/actions (données réelles)."""

from __future__ import annotations

from apps.api.snapshot import _yahoo_aliases


def test_crypto_variants():
    al = _yahoo_aliases("BTC/USDC", "crypto")
    assert "BTC-USD" in al and "BTC-USDT" in al and "BTC" in al
    assert al[0] == "BTC/USDC"            # l'original reste en tête


def test_forex_usd_base():
    al = _yahoo_aliases("EUR/USD", "forex")
    assert "EURUSD=X" in al
    al2 = _yahoo_aliases("USD/JPY", "forex")
    assert "JPY=X" in al2                 # USD/JPY → JPY=X (convention Yahoo)


def test_index_named():
    assert "^GSPC" in _yahoo_aliases("S&P 500", "index")
    assert "^VIX" in _yahoo_aliases("VIX", "index")


def test_commodity_named():
    assert "GC=F" in _yahoo_aliases("Gold", "commodity")
    assert "CL=F" in _yahoo_aliases("Crude Oil", "commodity")


def test_equity_share_class():
    al = _yahoo_aliases("BRK.B", "equity")
    assert "BRK-B" in al                  # classe d'action Yahoo
    assert "" not in al                   # jamais d'alias vide


def test_pas_de_doublon():
    al = _yahoo_aliases("AAPL", "equity")
    assert len(al) == len(set(al))
