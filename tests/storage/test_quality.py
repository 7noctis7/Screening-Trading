import pandas as pd
from datetime import datetime, timedelta, timezone
from packages.storage import validate_ohlcv, enforce, QualityError


def _df(n=50):
    idx = [datetime(2023, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(n)]
    return pd.DataFrame({
        "open": [100.0] * n, "high": [101.0] * n, "low": [99.0] * n,
        "close": [100.5] * n, "volume": [1000.0] * n}, index=pd.DatetimeIndex(idx))


def test_clean_passes():
    assert validate_ohlcv(_df(), "X", "1d").ok


def test_negative_price_blocks():
    df = _df(); df.iloc[3, df.columns.get_loc("close")] = -1
    rep = validate_ohlcv(df, "X", "1d")
    assert not rep.ok
    try:
        enforce(rep); raise AssertionError("aurait dû lever")
    except QualityError:
        pass


def test_ohlc_inconsistency_detected():
    df = _df(); df.iloc[2, df.columns.get_loc("high")] = 50.0  # high < low/close
    assert not validate_ohlcv(df, "X", "1d").ok


def test_duplicate_timestamps_detected():
    df = _df(5)
    df = pd.concat([df, df.iloc[[0]]])  # duplique un ts
    assert not validate_ohlcv(df, "X", "1d").ok
