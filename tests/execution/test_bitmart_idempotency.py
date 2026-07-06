"""Idempotence de BitmartBroker.submit() — sans ccxt ni réseau (faux exchange injecté).

Invariant : un même client_id ne produit qu'UN SEUL ordre net et rejoue le résultat
RÉEL du 1er submit (succès OU rejet). Jamais de FILLED fabriqué sur retry.
"""
from __future__ import annotations

import pytest

from packages.core.models import Order, OrderStatus, Side
from packages.execution.bitmart_broker import BitmartBroker


class FakeExchange:
    """Compte les appels create_order et rejoue un comportement paramétré par index d'appel."""

    def __init__(self, behavior):
        self.calls: list[dict] = []
        self._behavior = behavior          # callable(call_index) -> dict | raises

    def amount_to_precision(self, symbol, qty):   # noqa: D401
        return qty

    def fetch_ticker(self, symbol):
        return {"last": 100.0}                        # prix fake -> cout d'achat calculable

    def create_order(self, symbol, type, side, amount, price=None, params=None):  # noqa: A002
        # Regression 06/07 : un ACHAT marche DOIT porter un prix (BitMart veut le cout,
        # sinon ccxt leve createMarketBuyOrderRequiresPrice -> REJECTED silencieux).
        assert side != "buy" or price, "achat marche sans prix = bug cout BitMart"
        self.calls.append({"symbol": symbol, "type": type, "side": side,
                           "amount": amount, "params": params or {}})
        return self._behavior(len(self.calls) - 1)


def _live_broker(fake: FakeExchange) -> BitmartBroker:
    """Broker Bitmart en mode LIVE simulé : clés présentes, dry_run=False, exchange injecté."""
    b = BitmartBroker(api_key="k", api_secret="s", dry_run=False)
    b._ex = fake
    b._loaded = True
    assert b._live()
    return b


def _order(cid: str | None = None) -> Order:
    return Order("BTC/USDT", Side.LONG, 0.01, client_id=cid)


def test_success_then_retry_replays_filled_single_order():
    fake = FakeExchange(lambda i: {"status": "closed"})
    b = _live_broker(fake)
    r1 = b.submit(_order("cid-1"))
    assert r1.status is OrderStatus.FILLED
    r2 = b.submit(_order("cid-1"))                 # retry même client_id
    assert r2.status is OrderStatus.FILLED         # même résultat rejoué
    assert len(fake.calls) == 1                    # un seul ordre net


def test_rejected_then_retry_replays_rejected_opens_nothing():
    def behavior(i):
        raise Exception("insufficient funds")      # rejet exchange
    fake = FakeExchange(behavior)
    b = _live_broker(fake)
    r1 = b.submit(_order("cid-2"))
    assert r1.status is OrderStatus.REJECTED
    r2 = b.submit(_order("cid-2"))
    assert r2.status is OrderStatus.REJECTED        # le rejet reste un rejet
    assert len(fake.calls) == 1


def test_timeout_then_retry_single_net_order_same_result():
    def behavior(i):
        raise TimeoutError("network timeout")       # sort ambigu → mappé REJECTED
    fake = FakeExchange(behavior)
    b = _live_broker(fake)
    r1 = b.submit(_order("cid-3"))
    r2 = b.submit(_order("cid-3"))
    assert r1.status is r2.status                   # rejeu identique
    assert len(fake.calls) == 1                     # un seul ordre net (pas de doublon)


def test_client_order_id_forwarded_in_params():
    fake = FakeExchange(lambda i: {"status": "closed"})
    b = _live_broker(fake)
    b.submit(_order("cid-4"))
    assert fake.calls[0]["params"].get("clientOrderId") == "cid-4"


def test_no_client_id_no_idempotence():
    fake = FakeExchange(lambda i: {"status": "closed"})
    b = _live_broker(fake)
    b.submit(_order(None))
    b.submit(_order(None))
    assert len(fake.calls) == 2                     # sans client_id : chaque submit envoie un ordre


def test_open_status_replayed_as_submitted():
    fake = FakeExchange(lambda i: {"status": "open"})
    b = _live_broker(fake)
    r1 = b.submit(_order("cid-5"))
    assert r1.status is OrderStatus.SUBMITTED
    r2 = b.submit(_order("cid-5"))
    assert r2.status is OrderStatus.SUBMITTED       # statut non-fill rejoué tel quel
    assert len(fake.calls) == 1
