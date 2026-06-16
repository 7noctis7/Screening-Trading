"""Repository OHLCV — SQLite (stdlib, testable offline).

Couches medallion : bronze (brut immuable) → silver (validé/normalisé).
- **Idempotence** : clé primaire (symbol, timeframe, ts) + UPSERT → zéro doublon,
  rechargement sûr (incrémental ou backfill).
- **Multi-timeframe natif** : la même table porte tous les timeframes (1d/1h/4h…).
- Cible prod : DuckDB+Parquet via la MÊME interface `BarsRepository` (ADR à venir).

Cadence recommandée (cf. politique data) : daily en batch EOD pour le socle ;
1h/4h seulement pour les actifs/stratégies intraday.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.core.models import Bar

_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    symbol     TEXT NOT NULL,
    timeframe  TEXT NOT NULL,
    ts         TEXT NOT NULL,          -- ISO 8601 UTC
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    ingested_at TEXT NOT NULL,         -- traçabilité (lineage)
    PRIMARY KEY (symbol, timeframe, ts)
);
CREATE INDEX IF NOT EXISTS idx_{table}_sym_tf ON {table}(symbol, timeframe);
"""


class SqliteBarsRepository:
    """Bronze + silver dans deux tables. Bronze jamais réécrit, silver validé."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(db_path))
        for layer in ("bronze", "silver"):
            self.conn.executescript(_DDL.format(table=layer))
        self.conn.commit()

    def upsert(self, bars: list[Bar], layer: str = "silver") -> int:
        """UPSERT idempotent. Retourne le nombre de lignes écrites."""
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (b.instrument, b.timeframe, _iso(b.ts), b.open, b.high, b.low,
             b.close, b.volume, now)
            for b in bars
        ]
        self.conn.executemany(
            f"INSERT INTO {layer} "
            "(symbol,timeframe,ts,open,high,low,close,volume,ingested_at) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(symbol,timeframe,ts) DO UPDATE SET "
            "open=excluded.open, high=excluded.high, low=excluded.low, "
            "close=excluded.close, volume=excluded.volume, "
            "ingested_at=excluded.ingested_at",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def read(self, symbol: str, timeframe: str, layer: str = "silver",
             start: datetime | None = None, end: datetime | None = None) -> list[Bar]:
        q = (f"SELECT symbol,timeframe,ts,open,high,low,close,volume FROM {layer} "
             "WHERE symbol=? AND timeframe=?")
        params: list = [symbol, timeframe]
        if start:
            q += " AND ts>=?"; params.append(_iso(start))
        if end:
            q += " AND ts<=?"; params.append(_iso(end))
        q += " ORDER BY ts ASC"
        cur = self.conn.execute(q, params)
        return [
            Bar(r[0], r[1], datetime.fromisoformat(r[2]), r[3], r[4], r[5], r[6], r[7])
            for r in cur.fetchall()
        ]

    def last_ts(self, symbol: str, timeframe: str, layer: str = "silver") -> datetime | None:
        """Pour l'ingestion incrémentale : ne charger que le delta après ce ts."""
        cur = self.conn.execute(
            f"SELECT MAX(ts) FROM {layer} WHERE symbol=? AND timeframe=?",
            (symbol, timeframe))
        v = cur.fetchone()[0]
        return datetime.fromisoformat(v) if v else None

    def count(self, layer: str = "silver") -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {layer}").fetchone()[0]

    def close(self) -> None:
        self.conn.close()


def _iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()
