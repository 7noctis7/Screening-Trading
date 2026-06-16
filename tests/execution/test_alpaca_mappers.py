from types import SimpleNamespace
from packages.execution.alpaca_broker import position_from_alpaca, order_status_from_alpaca
from packages.core.models import OrderStatus, Side


def test_position_mapping():
    p = SimpleNamespace(symbol="AAPL", qty="10", avg_entry_price="150.5", side="long")
    pos = position_from_alpaca(p)
    assert pos.instrument == "AAPL" and pos.qty == 10.0
    assert pos.avg_price == 150.5 and pos.side is Side.LONG


def test_status_mapping():
    assert order_status_from_alpaca(SimpleNamespace(status="filled")) is OrderStatus.FILLED
    assert order_status_from_alpaca(SimpleNamespace(status="rejected")) is OrderStatus.REJECTED
    assert order_status_from_alpaca(SimpleNamespace(status="weird")) is OrderStatus.PENDING
