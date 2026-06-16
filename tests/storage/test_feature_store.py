from datetime import datetime, timedelta, timezone
from packages.core.models import Bar
from packages.data import data_providers
from packages.storage import FeatureStore, materialize_indicators
from packages.indicators import indicators


def _bars(n=300):
    p = data_providers.create("synthetic", seed=9)
    s = datetime(2022, 1, 1, tzinfo=timezone.utc)
    return p.fetch_ohlcv("AAPL", "1d", s, s + timedelta(days=n))


def test_materialize_and_read():
    fs = FeatureStore(":memory:")
    bars = _bars()
    specs = [{"name": "rsi", "params": {"period": 14}, "as": "rsi_14"},
             {"name": "sma", "params": {"period": 50}, "as": "sma_50"}]
    n = materialize_indicators(bars, fs, specs)
    assert n > 0
    assert set(fs.feature_names("AAPL", "1d")) == {"rsi_14", "sma_50"}


def test_no_nan_stored():
    fs = FeatureStore(":memory:")
    bars = _bars()
    materialize_indicators(bars, fs, [{"name": "sma", "params": {"period": 50}, "as": "sma_50"}])
    assert all(v == v for _, v in fs.read("AAPL", "1d", "sma_50"))


def test_store_equals_recompute_no_skew():
    fs = FeatureStore(":memory:")
    bars = _bars()
    materialize_indicators(bars, fs, [{"name": "rsi", "params": {"period": 14}, "as": "rsi"}])
    stored = dict(fs.read("AAPL", "1d", "rsi"))
    direct = indicators.create("rsi", period=14).compute(bars)
    ts = [b.ts for b in bars]
    assert all(abs(stored[ts[i]] - direct[i]) < 1e-9 for i in range(len(bars)) if ts[i] in stored)
