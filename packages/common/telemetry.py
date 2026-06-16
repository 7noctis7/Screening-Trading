"""Télémétrie minimale — compteurs, gauges, timers → snapshot pour dashboard de santé."""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager


class Metrics:
    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._timers: dict[str, list[float]] = defaultdict(list)

    def incr(self, name: str, by: float = 1.0) -> None:
        self._counters[name] += by

    def gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    @contextmanager
    def timer(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self._timers[name].append(time.perf_counter() - t0)

    def snapshot(self) -> dict:
        timers = {k: {"count": len(v), "avg_ms": round(1000 * sum(v) / len(v), 3)}
                  for k, v in self._timers.items() if v}
        return {"counters": dict(self._counters), "gauges": dict(self._gauges),
                "timers": timers}
