"""Repository OHLCV DuckDB — drop-in de SqliteBarsRepository pour le passage à l'échelle.

MÊME interface (`upsert`/`read`/`last_ts`/`count`/`close`) → on remplace SQLite par
DuckDB sans toucher aux consommateurs (backtest, feature store, etc.). DuckDB est
colonnaire et lit/écrit Parquet nativement → adapté aux gros volumes OHLCV/features.

Requiert `duckdb` (uv pip install duckdb). Code écrit pour l'environnement de prod ;
non exécuté hors-ligne. `export_parquet` matérialise une table en Parquet partitionné.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from packages.core.models import Bar

_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    symbol VARCHAR, timeframe VARCHAR, ts TIMESTAMP,
    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
    ingested_at TIMESTAMP,
    PRIMARY KEY (symbol, timeframe, ts)
);
"""


class DuckDBBarsRepository:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        import duckdb  # import local
        self.conn = duckdb.connect(str(db_path))
        for layer in ("bronze", "silver"):
            self.conn.execute(_DDL.format(table=layer))

    def upsert(self, bars: list[Bar], layer: str = "silver") -> int:
        now = datetime.now(timezone.utc)
        rows = [(b.instrument, b.timeframe, b.ts, b.open, b.high, b.low,
                 b.close, b.volume, now) for b in bars]
        self.conn.executemany(
            f"INSERT INTO {layer} VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT (symbol, timeframe, ts) DO UPDATE SET "
            "open=excluded.open, high=excluded.high, low=excluded.low, "
            "close=excluded.close, volume=excluded.volume, "
            "ingested_at=excluded.ingested_at", rows)
        return len(rows)

    def read(self, symbol: str, timeframe: str, layer: str = "silver",
             start: datetime | None = None, end: datetime | None = None) -> list[Bar]:
        q = (f"SELECT symbol,timeframe,ts,open,high,low,close,volume FROM {layer} "
             "WHERE symbol=? AND timeframe=?")
        params: list = [symbol, timeframe]
        if start:
            q += " AND ts>=?"; params.append(start)
        if end:
            q += " AND ts<=?"; params.append(end)
        q += " ORDER BY ts"
        rows = self.conn.execute(q, params).fetchall()
        return [Bar(r[0], r[1], r[2] if isinstance(r[2], datetime)
                    else datetime.fromisoformat(str(r[2])), r[3], r[4], r[5], r[6], r[7])
                for r in rows]

    def last_ts(self, symbol: str, timeframe: str, layer: str = "silver") -> datetime | None:
        r = self.conn.execute(
            f"SELECT MAX(ts) FROM {layer} WHERE symbol=? AND timeframe=?",
            [symbol, timeframe]).fetchone()
        return r[0] if r and r[0] else None

    def count(self, layer: str = "silver") -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {layer}").fetchone()[0]

    def export_parquet(self, layer: str, out_dir: str | Path) -> None:
        """Matérialise une couche en Parquet partitionné par symbole (analytics/DVC)."""
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        self.conn.execute(
            f"COPY (SELECT * FROM {layer}) TO '{out_dir}' "
            "(FORMAT PARQUET, PARTITION_BY (symbol), OVERWRITE_OR_IGNORE)")

    def close(self) -> None:
        self.conn.close()
