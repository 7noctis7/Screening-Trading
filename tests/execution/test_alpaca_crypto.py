"""AlpacaBroker crypto-capable — TIF asset-class-aware (GTC crypto, DAY actions), sans réseau.

Alpaca REJETTE `TimeInForce.DAY` pour la crypto (marché 24/7 → GTC obligatoire). On vérifie
que les deux chemins d'ordre (submit par qté, submit_notional par montant) choisissent le bon TIF.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("alpaca", reason="SDK alpaca-py absent (env minimal) — couvert en CI")
from alpaca.trading.enums import TimeInForce  # noqa: E402

from packages.core.models import Order, Side
from packages.execution.alpaca_broker import AlpacaBroker, _is_crypto_symbol


class _FakeClient:
    """Capture la requête d'ordre au lieu de l'envoyer au réseau."""

    def __init__(self):
        self.reqs = []

    def submit_order(self, req):
        self.reqs.append(req)
        return SimpleNamespace(status="filled")


def _broker() -> AlpacaBroker:
    # bypass __init__ (pas de TradingClient/réseau) : on n'exerce que la construction de requête.
    b = AlpacaBroker.__new__(AlpacaBroker)
    b.is_paper = True
    b._client = _FakeClient()
    return b


def test_is_crypto_symbol():
    assert _is_crypto_symbol("BTC/USD")
    assert _is_crypto_symbol("ETH/USD")
    assert not _is_crypto_symbol("AAPL")
    assert not _is_crypto_symbol("")


def test_submit_crypto_uses_gtc():
    b = _broker()
    b.submit(Order("BTC/USD", Side.LONG, 0.01, client_id="c1"))
    assert b._client.reqs[0].time_in_force == TimeInForce.GTC


def test_submit_equity_uses_day():
    b = _broker()
    b.submit(Order("AAPL", Side.LONG, 10.0, client_id="c2"))
    assert b._client.reqs[0].time_in_force == TimeInForce.DAY


def test_submit_notional_crypto_uses_gtc_and_notional():
    b = _broker()
    b.submit_notional("ETH/USD", Side.LONG, 250.0)
    req = b._client.reqs[0]
    assert req.time_in_force == TimeInForce.GTC
    assert float(req.notional) == 250.0


def test_submit_notional_equity_uses_day():
    b = _broker()
    b.submit_notional("SPY", Side.LONG, 500.0)
    assert b._client.reqs[0].time_in_force == TimeInForce.DAY
