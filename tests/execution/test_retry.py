from packages.execution import submit_with_retries
from packages.core.models import Order, OrderStatus, Side


class _Flaky:
    name = "flaky"
    def __init__(self, fail_n): self.fail_n = fail_n; self.calls = 0
    def submit(self, order):
        self.calls += 1
        if self.calls <= self.fail_n:
            raise ConnectionError("réseau")
        order.status = OrderStatus.FILLED
        return order


class _Rejecting:
    name = "rej"
    def submit(self, order):
        order.status = OrderStatus.REJECTED
        return order


def test_retries_then_succeeds():
    b = _Flaky(fail_n=2)
    o = submit_with_retries(b, Order("AAPL", Side.LONG, 1), attempts=3, sleep=lambda s: None)
    assert o.status is OrderStatus.FILLED and b.calls == 3
    assert o.client_id  # client_id généré → idempotence


def test_gives_up_after_attempts():
    b = _Flaky(fail_n=5)
    o = submit_with_retries(b, Order("AAPL", Side.LONG, 1), attempts=3, sleep=lambda s: None)
    assert o.status is OrderStatus.REJECTED


def test_rejected_is_retried_then_abandoned():
    o = submit_with_retries(_Rejecting(), Order("AAPL", Side.LONG, 1),
                            attempts=2, sleep=lambda s: None)
    assert o.status is OrderStatus.REJECTED
