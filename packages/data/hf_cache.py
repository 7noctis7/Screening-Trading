"""Cache OHLCV souverain via un dataset Hugging Face (gratuit, versionné).

But : éliminer la dépendance fragile à yfinance en CI (rate-limit) et rendre les données
reproductibles. Le dataset est PUBLIC → la **lecture** ne requiert aucun token ; seule
l'**écriture** (rafraîchissement) utilise `HF_TOKEN`.

- `read_parquet_rows(name)` : lit `<name>.parquet` du dataset HF (via DuckDB sur HTTP, sans token).
- `write_sqlite(rows, db)`  : matérialise les lignes en SQLite `prices` (schéma lu par le snapshot).
Le module ne fait AUCUN import lourd au chargement (duckdb/pandas importés à la demande).
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DATASET = "Noctis777/screening-trading-cache"

_DDL = """CREATE TABLE IF NOT EXISTS prices(
  symbol TEXT NOT NULL, date TEXT NOT NULL,
  open REAL, high REAL, low REAL, close REAL, volume REAL,
  PRIMARY KEY(symbol, date));
CREATE INDEX IF NOT EXISTS ix_prices_symbol ON prices(symbol);"""


def dataset(dataset_id: str | None = None) -> str:
    return dataset_id or os.environ.get("HF_DATASET", DEFAULT_DATASET)


def parquet_url(name: str, dataset_id: str | None = None) -> str:
    return f"https://huggingface.co/datasets/{dataset(dataset_id)}/resolve/main/{name}.parquet"


def write_sqlite(rows, db_path: str | Path) -> int:
    """Écrit des lignes {symbol, date|ts, open..volume} dans une base SQLite `prices` (idempotent)."""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    try:
        con.executescript(_DDL)
        recs = []
        for r in rows:
            sym = r.get("symbol")
            d = r.get("date") or r.get("ts")
            if not sym or not d:
                continue
            recs.append((sym, str(d)[:10], r.get("open"), r.get("high"),
                         r.get("low"), r.get("close"), r.get("volume")))
        con.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)", recs)
        con.commit()
        return len(recs)
    finally:
        con.close()


def read_parquet_rows(name: str, dataset_id: str | None = None) -> list[dict]:
    """Lit le parquet public du dataset HF → lignes normalisées. [] si indisponible (repli propre)."""
    url = parquet_url(name, dataset_id)
    try:
        import duckdb
        q = duckdb.sql(
            "SELECT symbol, CAST(date AS VARCHAR) AS date, open, high, low, close, volume "
            f"FROM read_parquet('{url}')")
        cols = list(q.columns)
        return [dict(zip(cols, row)) for row in q.fetchall()]
    except Exception:  # noqa: BLE001 — dataset absent/vide/hors-ligne → repli (yfinance prendra le relais)
        return []
