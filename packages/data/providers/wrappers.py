"""Wrappers de providers — caching, fallback, rate-limiting.

Enveloppent n'importe quel `DataProvider` (même interface) :
- `FallbackProvider` : essaie plusieurs sources dans l'ordre (yfinance → Finnhub → …).
- `CachingProvider` : mémoïse les requêtes + persiste optionnellement en silver.
- `RateLimiter` / `RateLimitedProvider` : respecte un quota (intervalle min entre appels).

Toute la logique est testable hors-ligne (horloge injectable, provider amont synthétique).
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from packages.common.logging import get_logger
from packages.core.models import Bar

log = get_logger("data.wrappers")


class FallbackProvider:
    """Essaie chaque provider dans l'ordre ; renvoie le 1er résultat non vide."""

    name = "fallback"

    def __init__(self, providers: list) -> None:
        if not providers:
            raise ValueError("au moins un provider requis")
        self.providers = providers

    def supports(self, symbol: str) -> bool:
        return any(p.supports(symbol) for p in self.providers)

    def fetch_ohlcv(self, symbol, timeframe, start, end=None) -> list[Bar]:
        last_exc: Exception | None = None
        for p in self.providers:
            try:
                bars = p.fetch_ohlcv(symbol, timeframe, start, end)
                if bars:
                    return bars
            except Exception as e:  # noqa: BLE001
                last_exc = e
                log.warning("provider en échec", extra={"extra": {
                    "provider": getattr(p, "name", "?"), "symbol": symbol,
                    "err": str(e)[:120]}})
        if last_exc:
            log.warning("tous les providers ont échoué", extra={"extra": {"symbol": symbol}})
        return []


class CachingProvider:
    """Mémoïse (symbol, timeframe, start, end). Persiste en silver si repo fourni."""

    name = "cached"

    def __init__(self, upstream, repo=None) -> None:
        self.upstream = upstream
        self.repo = repo
        self._cache: dict[tuple, list[Bar]] = {}
        self.hits = 0
        self.misses = 0

    def supports(self, symbol: str) -> bool:
        return self.upstream.supports(symbol)

    def fetch_ohlcv(self, symbol, timeframe, start, end=None) -> list[Bar]:
        key = (symbol, timeframe, _iso(start), _iso(end) if end else None)
        if key in self._cache:
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        bars = self.upstream.fetch_ohlcv(symbol, timeframe, start, end)
        self._cache[key] = bars
        if self.repo is not None and bars:
            self.repo.upsert(bars, layer="silver")
        return bars


class RateLimiter:
    """Intervalle minimal entre appels (quota = max_calls / period_s). Horloge injectable."""

    def __init__(self, max_calls: int, period_s: float,
                 clock: Callable[[], float] | None = None) -> None:
        self.min_interval = period_s / max_calls if max_calls > 0 else 0.0
        self._clock = clock or _monotonic
        self._last: float | None = None   # None = aucun appel encore → pas d'attente

    def wait_time(self) -> float:
        """Secondes à attendre avant le prochain appel (0 si OK)."""
        if self._last is None:
            return 0.0
        delta = self._clock() - self._last
        return max(0.0, self.min_interval - delta)

    def acquire(self) -> None:
        w = self.wait_time()
        if w > 0:
            import time
            time.sleep(w)
        self._last = self._clock()


class RateLimitedProvider:
    """Applique un RateLimiter avant chaque fetch."""

    name = "rate_limited"

    def __init__(self, upstream, limiter: RateLimiter) -> None:
        self.upstream = upstream
        self.limiter = limiter

    def supports(self, symbol: str) -> bool:
        return self.upstream.supports(symbol)

    def fetch_ohlcv(self, symbol, timeframe, start, end=None) -> list[Bar]:
        self.limiter.acquire()
        return self.upstream.fetch_ohlcv(symbol, timeframe, start, end)


def _iso(ts: datetime | None) -> str | None:
    return ts.isoformat() if ts else None


def _monotonic() -> float:
    import time
    return time.monotonic()
