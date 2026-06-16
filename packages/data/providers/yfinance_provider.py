"""Provider yfinance (réel). Normalise en OHLCV UTC. Requiert `yfinance` + réseau.

La conversion DataFrame→Bar (`df_to_bars`) est PURE et testable hors-ligne en lui
injectant un DataFrame factice (pas besoin de yfinance pour tester la normalisation).
"""

from __future__ import annotations

from datetime import datetime

from packages.core.models import Bar
from packages.data.registry import data_providers

_TF_MAP = {"1d": "1d", "1h": "1h", "4h": "1h", "5m": "5m", "1m": "1m"}


def df_to_bars(df, symbol: str, timeframe: str) -> list[Bar]:
    """Convertit un DataFrame (index temporel, colonnes OHLCV) en barres UTC."""
    bars: list[Bar] = []
    for ts, row in df.iterrows():
        ts_utc = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        bars.append(Bar(symbol, timeframe, ts_utc.to_pydatetime(),
                        float(row["Open"]), float(row["High"]), float(row["Low"]),
                        float(row["Close"]), float(row["Volume"])))
    return bars


@data_providers.register("yfinance")
class YFinanceProvider:
    name = "yfinance"

    def supports(self, symbol: str) -> bool:
        return True

    def fetch_ohlcv(self, symbol, timeframe, start, end=None) -> list[Bar]:
        import yfinance as yf  # import local → core/tests restent sans dépendance
        interval = _TF_MAP.get(timeframe, "1d")
        df = yf.download(symbol, start=start, end=end, interval=interval,
                         auto_adjust=True, progress=False)
        if df is None or df.empty:
            return []
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)  # aplatir multi-index
        return df_to_bars(df, symbol, timeframe)
