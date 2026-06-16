"""Soumission d'ordre avec retries idempotents + backoff.

L'idempotence vient du `client_id` (le broker ne re-remplit pas un client_id déjà vu).
Donc rejouer après une erreur réseau est SÛR. `sleep` injectable pour les tests.
"""

from __future__ import annotations

import uuid
from typing import Callable

from packages.core.models import Order, OrderStatus
from packages.common.logging import get_logger

log = get_logger("execution.retry")


def submit_with_retries(broker, order: Order, attempts: int = 3,
                        backoff_s: float = 1.0,
                        sleep: Callable[[float], None] | None = None) -> Order:
    if not order.client_id:
        order.client_id = uuid.uuid4().hex   # garantit l'idempotence
    sleep = sleep or _real_sleep
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            result = broker.submit(order)
            if result.status is not OrderStatus.REJECTED:
                return result
            last_exc = RuntimeError(f"ordre rejeté: {order.instrument}")
        except Exception as e:  # noqa: BLE001
            last_exc = e
            log.warning("submit échec, retry", extra={"extra": {
                "attempt": i + 1, "client_id": order.client_id, "err": str(e)[:120]}})
        if i < attempts - 1:
            sleep(backoff_s * (2 ** i))   # backoff exponentiel
    order.status = OrderStatus.REJECTED
    if last_exc:
        log.warning("submit abandonné", extra={"extra": {"client_id": order.client_id}})
    return order


def _real_sleep(s: float) -> None:
    import time
    time.sleep(s)
