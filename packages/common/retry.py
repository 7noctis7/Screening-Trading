"""Retry avec backoff exponentiel — robustesse réseau broker/API, 0 dépendance.

`retry()` ré-essaie une fonction sur exception (timeout, rate-limit transitoire), délai
exponentiel borné. `sleep` injectable → testable sans attente réelle. Relève la dernière
exception si tous les essais échouent (jamais silencieux).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


def retry(
    fn: Callable[[], Any],
    attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 16.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Exécute `fn()` jusqu'à `attempts` fois. Backoff base·2^(n-1), borné `max_delay`.

    Succès → résultat. Échec total → relève la dernière exception capturée.
    """
    if attempts < 1:
        raise ValueError("attempts >= 1")
    last: BaseException | None = None
    for n in range(attempts):
        try:
            return fn()
        except exceptions as e:  # noqa: BLE001 - on relève après épuisement
            last = e
            if n < attempts - 1:
                sleep(min(base_delay * (2 ** n), max_delay))
    assert last is not None
    raise last
