"""Fills partiels dans LiveTradingEngine — ouverture à la qté RÉELLE, jamais supposer plein.

Contrats :
- FILLED plein → position à la qté demandée.
- PARTIALLY_FILLED + filled_qty>0 → position à la qté remplie (reliquat ignoré).
- PARTIALLY_FILLED + filled_qty=None → AUCUNE position + alerte CRITICAL sur le bus.
- PARTIALLY_FILLED + filled_qty=0 → aucune position.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from packages.common.event_bus import EventBus, Topic
from packages.core.models import Order, OrderStatus, Side
from packages.execution import LiveTradingEngine
from packages.storage.journal import TradeJournal


def _engine(bus=None) -> LiveTradingEngine:
    # journal in-memory : ne touche pas data/journal.db.
    return LiveTradingEngine(strategy=None, sizer=None, risk_engine=None,
                             broker=None, journal=TradeJournal(), bus=bus)


def _sig():
    return SimpleNamespace(stop=90.0, target=110.0, features={})


def _bar():
    return SimpleNamespace(close=100.0, ts=datetime(2026, 1, 2, tzinfo=timezone.utc))


def _res(status: OrderStatus, filled_qty=None) -> Order:
    return Order("AAPL", Side.LONG, 10.0, status=status, filled_qty=filled_qty)


def test_full_fill_opens_requested_qty():
    eng = _engine()
    eng._record_open("AAPL", _res(OrderStatus.FILLED), _sig(), _bar(), qty=10.0)
    assert "AAPL" in eng._open
    assert eng._open["AAPL"].qty == 10.0


def test_full_fill_uses_reported_filled_qty_when_present():
    eng = _engine()
    eng._record_open("AAPL", _res(OrderStatus.FILLED, filled_qty=10.0), _sig(), _bar(), qty=10.0)
    assert eng._open["AAPL"].qty == 10.0


def test_partial_fill_opens_at_filled_qty():
    eng = _engine()
    eng._record_open("AAPL", _res(OrderStatus.PARTIALLY_FILLED, filled_qty=4.0),
                     _sig(), _bar(), qty=10.0)
    assert eng._open["AAPL"].qty == 4.0            # ouvre à la qté RÉELLE, pas 10


def test_partial_fill_unknown_qty_opens_nothing_and_alerts_critical():
    bus = EventBus()
    events = []
    bus.subscribe(Topic.PARTIAL_FILL_UNKNOWN, lambda ev: events.append(ev))
    eng = _engine(bus=bus)
    eng._record_open("AAPL", _res(OrderStatus.PARTIALLY_FILLED, filled_qty=None),
                     _sig(), _bar(), qty=10.0)
    assert "AAPL" not in eng._open                  # jamais supposer un fill plein
    assert len(events) == 1
    assert events[0].payload["symbol"] == "AAPL"


def test_partial_fill_zero_qty_opens_nothing():
    eng = _engine()
    eng._record_open("AAPL", _res(OrderStatus.PARTIALLY_FILLED, filled_qty=0.0),
                     _sig(), _bar(), qty=10.0)
    assert "AAPL" not in eng._open


def test_partial_fill_flows_through_try_open():
    """Intégration : broker renvoyant un fill partiel → position à la qté réelle."""
    class _Sizer:
        def size(self, sig, equity, price, regime):
            return 10.0

    class _Risk:
        def approve(self, *a, **k):
            return SimpleNamespace(approved=True)

    class _PartialBroker:
        name = "fake"

        def equity(self):
            return 100_000.0

        def positions(self):
            return []

        def submit(self, order):
            order.status = OrderStatus.PARTIALLY_FILLED
            order.filled_qty = 4.0
            return order

    eng = LiveTradingEngine(strategy=None, sizer=_Sizer(), risk_engine=_Risk(),
                            broker=_PartialBroker(), journal=TradeJournal())
    eng._try_open("AAPL", _sig(), _bar(), regime=None)
    assert eng._open["AAPL"].qty == 4.0
