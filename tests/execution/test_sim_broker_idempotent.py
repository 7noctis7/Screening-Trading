from packages.execution import SimBroker, CostModel
from packages.core.models import Order, Side


def test_same_client_id_fills_once():
    b = SimBroker(cash=100_000, costs=CostModel())
    b.mark("AAPL", 100)
    b.submit(Order("AAPL", Side.LONG, 10, client_id="x"))
    b.submit(Order("AAPL", Side.LONG, 10, client_id="x"))   # retry → no-op
    assert b.position("AAPL").qty == 10


def test_distinct_client_ids_accumulate():
    b = SimBroker(cash=100_000, costs=CostModel())
    b.mark("AAPL", 100)
    b.submit(Order("AAPL", Side.LONG, 10, client_id="a"))
    b.submit(Order("AAPL", Side.LONG, 5, client_id="b"))
    assert b.position("AAPL").qty == 15
