from datetime import datetime, timedelta, timezone
from packages.data import data_providers
from packages.storage import SqliteBarsRepository


def _bars(symbol="AAPL", days=100):
    p = data_providers.create("synthetic", seed=7)
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    return p.fetch_ohlcv(symbol, "1d", start, start + timedelta(days=days))


def test_upsert_idempotent():
    repo = SqliteBarsRepository(":memory:")
    bars = _bars()
    repo.upsert(bars, "silver")
    c1 = repo.count("silver")
    repo.upsert(bars, "silver")          # re-charge les mêmes → pas de doublon
    assert repo.count("silver") == c1 == len(bars)


def test_read_roundtrip():
    repo = SqliteBarsRepository(":memory:")
    bars = _bars()
    repo.upsert(bars, "silver")
    back = repo.read("AAPL", "1d", "silver")
    assert len(back) == len(bars)
    assert abs(back[0].close - bars[0].close) < 1e-9
    assert back == sorted(back, key=lambda b: b.ts)  # ordre croissant


def test_last_ts_for_incremental():
    repo = SqliteBarsRepository(":memory:")
    bars = _bars()
    repo.upsert(bars, "silver")
    assert repo.last_ts("AAPL", "1d", "silver") == bars[-1].ts


def test_multi_timeframe_isolation():
    repo = SqliteBarsRepository(":memory:")
    repo.upsert(_bars(), "silver")
    assert repo.read("AAPL", "1h", "silver") == []  # autre timeframe = vide
