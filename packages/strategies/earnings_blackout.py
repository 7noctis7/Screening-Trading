"""Filtre « blackout earnings » — éviter le risque BINAIRE des annonces de résultats.

Le backtest PEAD montre que détenir à travers les résultats sous-performe (edge négatif) : la
best practice de robustesse est de **ne pas garder une position nue** juste avant une annonce
(gap surprise type −28 %). Ce module signale les positions dont les résultats sont imminents.

Dates via yfinance (gratuit) ; dégrade proprement hors-ligne. À utiliser comme filtre d'entrée
(ne pas ouvrir si earnings < N jours) et comme alerte sur les positions détenues.
"""

from __future__ import annotations

from datetime import datetime, timezone


def days_to_next_earnings(symbol: str, now: datetime | None = None) -> int | None:
    """Nombre de jours jusqu'aux prochains résultats (yfinance). None si inconnu/hors-ligne."""
    now = now or datetime.now(timezone.utc)
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).get_earnings_dates(limit=12)
        if df is None or df.empty:
            return None
        fut = [ts.to_pydatetime() for ts in df.index if ts.to_pydatetime().date() >= now.date()]
        if not fut:
            return None
        return (min(fut).date() - now.date()).days
    except Exception:  # noqa: BLE001
        return None


def flag_positions(symbols: list[str], within: int = 7, now: datetime | None = None) -> list[dict]:
    """Positions dont les résultats tombent dans `within` jours → risque binaire à gérer."""
    out = []
    for s in symbols:
        d = days_to_next_earnings(s, now)
        if d is not None and 0 <= d <= within:
            out.append({"symbol": s, "days": d})
    out.sort(key=lambda x: x["days"])
    return out
