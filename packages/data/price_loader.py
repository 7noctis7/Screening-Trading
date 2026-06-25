"""Chargement de barres OHLCV : base locale d'abord, repli yfinance sinon.

Mutualisé entre l'event-study et les backtests. Le repli yfinance débloque les tickers
HORS univers (small/mid-caps absentes de la base) — indispensable pour tester un signal
là où il a une chance de vivre. Best-effort : [] si tout échoue, jamais bloquant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def load_bars(ticker: str, years: int = 10):
    """Barres d'un ticker : base (YAHOO.db) si ≥60 barres, sinon yfinance. []."""
    try:
        from apps.api.snapshot import _price_db_path
        from packages.data.providers.db_provider import DBPriceProvider
        db = _price_db_path()
        if db:
            start = datetime.now(UTC) - timedelta(days=365 * years)
            bars = DBPriceProvider(db).fetch_ohlcv(ticker, "1d", start)
            if len(bars) >= 60:
                return bars
    except Exception:  # noqa: BLE001 - repli yfinance ci-dessous
        pass
    return load_bars_yf(ticker, years)


def load_bars_yf(ticker: str, years: int = 10):
    """Repli prix via yfinance (tickers hors base). []."""
    try:
        from types import SimpleNamespace

        import yfinance as yf
        df = yf.Ticker(ticker).history(period=f"{years}y", auto_adjust=True)
        if df is None or df.empty:
            return []
        return [SimpleNamespace(ts=ix.to_pydatetime(), close=float(r["Close"]),
                                volume=float(r.get("Volume", 0.0) or 0.0))
                for ix, r in df.iterrows()]
    except Exception:  # noqa: BLE001 - best-effort
        return []
