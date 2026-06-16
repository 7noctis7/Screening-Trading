from datetime import datetime, timedelta, timezone
from packages.data import (
    CachingProvider, FallbackProvider, RateLimitedProvider, RateLimiter, data_providers,
)

START = datetime(2023, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(days=60)


class _Failing:
    name = "failing"
    def supports(self, s): return True
    def fetch_ohlcv(self, *a, **k): raise RuntimeError("down")


class _Empty:
    name = "empty"
    def supports(self, s): return True
    def fetch_ohlcv(self, *a, **k): return []


def test_fallback_skips_failing_and_empty():
    good = data_providers.create("synthetic", seed=1)
    fb = FallbackProvider([_Failing(), _Empty(), good])
    bars = fb.fetch_ohlcv("AAPL", "1d", START, END)
    assert len(bars) > 0


def test_fallback_all_fail_returns_empty():
    fb = FallbackProvider([_Failing(), _Empty()])
    assert fb.fetch_ohlcv("AAPL", "1d", START, END) == []


def test_caching_hits():
    cp = CachingProvider(data_providers.create("synthetic", seed=1))
    cp.fetch_ohlcv("AAPL", "1d", START, END)
    cp.fetch_ohlcv("AAPL", "1d", START, END)   # même clé → hit
    assert cp.hits == 1 and cp.misses == 1


def test_caching_persists_to_repo():
    from packages.storage import SqliteBarsRepository
    repo = SqliteBarsRepository(":memory:")
    cp = CachingProvider(data_providers.create("synthetic", seed=1), repo=repo)
    cp.fetch_ohlcv("AAPL", "1d", START, END)
    assert repo.count("silver") > 0


def test_rate_limiter_wait_logic():
    t = {"now": 0.0}
    rl = RateLimiter(max_calls=2, period_s=1.0, clock=lambda: t["now"])  # min_interval 0.5
    assert rl.wait_time() == 0.0
    rl._last = 0.0
    t["now"] = 0.1
    assert abs(rl.wait_time() - 0.4) < 1e-9
    t["now"] = 0.6
    assert rl.wait_time() == 0.0
