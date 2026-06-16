import pytest
from packages.storage import make_bars_repository


def test_sqlite_backend():
    repo = make_bars_repository("sqlite", ":memory:")
    assert repo.count("silver") == 0


def test_unknown_backend_raises():
    with pytest.raises(ValueError):
        make_bars_repository("oracle")


def test_duckdb_same_interface_if_installed():
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return  # skip offline : duckdb non installé
    from datetime import datetime, timedelta, timezone
    from packages.data import data_providers
    repo = make_bars_repository("duckdb", ":memory:")
    bars = data_providers.create("synthetic", seed=1).fetch_ohlcv(
        "AAPL", "1d", datetime(2023, 1, 1, tzinfo=timezone.utc),
        datetime(2023, 1, 1, tzinfo=timezone.utc) + timedelta(days=50))
    repo.upsert(bars, "silver")
    c1 = repo.count("silver")
    repo.upsert(bars, "silver")                 # idempotent
    assert repo.count("silver") == c1 == len(bars)
