"""Reproductibilité = priorité #1. Le provider synthétique doit être déterministe
indépendamment du PYTHONHASHSEED (pas de hash() builtin sur les symboles)."""

from datetime import datetime, timedelta, timezone
from packages.data import data_providers


def test_synthetic_is_deterministic():
    start = datetime(2022, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=120)
    a = data_providers.create("synthetic", seed=7).fetch_ohlcv("AAPL", "1d", start, end)
    b = data_providers.create("synthetic", seed=7).fetch_ohlcv("AAPL", "1d", start, end)
    assert [x.close for x in a] == [x.close for x in b]


def test_different_symbols_differ():
    start = datetime(2022, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=120)
    a = data_providers.create("synthetic", seed=7).fetch_ohlcv("AAPL", "1d", start, end)
    b = data_providers.create("synthetic", seed=7).fetch_ohlcv("MSFT", "1d", start, end)
    assert [x.close for x in a] != [x.close for x in b]
