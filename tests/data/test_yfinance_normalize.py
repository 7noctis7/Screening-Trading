import pandas as pd
from datetime import datetime, timezone
from packages.data.providers.yfinance_provider import df_to_bars


def test_df_to_bars_normalizes_utc():
    idx = pd.DatetimeIndex([datetime(2023, 1, 2), datetime(2023, 1, 3)])
    df = pd.DataFrame({"Open": [10, 11], "High": [12, 13], "Low": [9, 10],
                       "Close": [11, 12], "Volume": [100, 200]}, index=idx)
    bars = df_to_bars(df, "AAPL", "1d")
    assert len(bars) == 2
    assert bars[0].instrument == "AAPL" and bars[0].close == 11.0
    assert bars[0].ts.tzinfo is not None  # UTC localisé
