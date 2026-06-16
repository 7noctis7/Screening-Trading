"""Snapshots d'univers datés — membership point-in-time (anti survivorship-bias).

On stocke QUI était dans l'univers à chaque date de build. Backtester sur la
composition d'aujourd'hui projetée dans le passé = biais du survivant. Ce repo
permet de rejouer l'univers tel qu'il était.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.core.models import AssetClass, Instrument

_DDL = """
CREATE TABLE IF NOT EXISTS universe_snapshot (
    as_of TEXT NOT NULL, symbol TEXT NOT NULL, asset_class TEXT NOT NULL,
    venue TEXT NOT NULL, currency TEXT NOT NULL,
    PRIMARY KEY (as_of, symbol, venue)
);
CREATE INDEX IF NOT EXISTS idx_univ_asof ON universe_snapshot(as_of);
"""


class UniverseRepository:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(_DDL)
        self.conn.commit()

    def save_snapshot(self, instruments: list[Instrument],
                      as_of: datetime | None = None) -> str:
        as_of = as_of or datetime.now(timezone.utc)
        key = as_of.date().isoformat()
        rows = [(key, i.symbol, i.asset_class.value, i.venue, i.currency)
                for i in instruments]
        self.conn.executemany(
            "INSERT OR REPLACE INTO universe_snapshot VALUES (?,?,?,?,?)", rows)
        self.conn.commit()
        return key

    def load_snapshot(self, as_of: str) -> list[Instrument]:
        cur = self.conn.execute(
            "SELECT symbol,asset_class,venue,currency FROM universe_snapshot "
            "WHERE as_of=? ORDER BY symbol", (as_of,))
        return [Instrument(r[0], AssetClass(r[1]), r[2], r[3]) for r in cur.fetchall()]

    def latest_date(self) -> str | None:
        v = self.conn.execute("SELECT MAX(as_of) FROM universe_snapshot").fetchone()[0]
        return v

    def close(self) -> None:
        self.conn.close()
