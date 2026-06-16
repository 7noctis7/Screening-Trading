"""Fabrique de repository OHLCV — choix du backend en config (sqlite | duckdb).

Les deux exposent la MÊME interface → on bascule SQLite (dev/test) ↔ DuckDB (prod
gros volumes) sans toucher aux consommateurs.
"""

from __future__ import annotations

from pathlib import Path


def make_bars_repository(backend: str = "sqlite", db_path: str | Path = ":memory:"):
    if backend == "sqlite":
        from packages.storage.bars_repo import SqliteBarsRepository
        return SqliteBarsRepository(db_path)
    if backend == "duckdb":
        from packages.storage.duckdb_bars_repo import DuckDBBarsRepository
        return DuckDBBarsRepository(db_path)
    raise ValueError(f"backend inconnu: {backend} (sqlite|duckdb)")
