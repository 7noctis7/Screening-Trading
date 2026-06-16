"""Throttling anti-spam — supprime les doublons d'une même clé dans une fenêtre TTL.

Horloge injectable → testable sans attente réelle.
"""

from __future__ import annotations

from typing import Callable


class Throttle:
    def __init__(self, ttl_s: float = 300.0, clock: Callable[[], float] | None = None) -> None:
        self.ttl_s = ttl_s
        self._clock = clock or _monotonic
        self._last: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        last = self._last.get(key)
        if last is not None and now - last < self.ttl_s:
            return False
        self._last[key] = now
        return True


def _monotonic() -> float:
    import time
    return time.monotonic()
