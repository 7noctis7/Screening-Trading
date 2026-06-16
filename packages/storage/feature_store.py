"""Feature store (couche GOLD) — features cohérentes backtest ↔ live (anti-skew).

Stocke n'importe quelle feature nommée par (symbol, timeframe, ts, name) → valeur.
Les indicateurs sont calculés point-in-time depuis SILVER (aucun look-ahead garanti
par les indicateurs eux-mêmes) puis matérialisés ici. La MÊME table sert au backtest
et au live → pas de training/serving skew (López de Prado).

NaN de warm-up non stockés (une feature absente à `t` = pas encore disponible).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.core.models import Bar
from packages.indicators.registry import indicators

_DDL = """
CREATE TABLE IF NOT EXISTS feature (
    symbol TEXT NOT NULL, timeframe TEXT NOT NULL, ts TEXT NOT NULL,
    name TEXT NOT NULL, value REAL NOT NULL, computed_at TEXT NOT NULL,
    PRIMARY KEY (symbol, timeframe, ts, name)
);
CREATE INDEX IF NOT EXISTS idx_feat_sym ON feature(symbol, timeframe, name);
"""


class FeatureStore:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(_DDL)
        self.conn.commit()

    def write(self, symbol: str, timeframe: str, name: str,
              ts_values: list[tuple[datetime, float]]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        rows = [(symbol, timeframe, _iso(ts), name, float(v), now)
                for ts, v in ts_values if v == v]  # exclut NaN
        self.conn.executemany(
            "INSERT OR REPLACE INTO feature VALUES (?,?,?,?,?,?)", rows)
        self.conn.commit()
        return len(rows)

    def read(self, symbol: str, timeframe: str, name: str) -> list[tuple[datetime, float]]:
        cur = self.conn.execute(
            "SELECT ts,value FROM feature WHERE symbol=? AND timeframe=? AND name=? "
            "ORDER BY ts", (symbol, timeframe, name))
        return [(datetime.fromisoformat(r[0]), r[1]) for r in cur.fetchall()]

    def feature_names(self, symbol: str, timeframe: str) -> list[str]:
        cur = self.conn.execute(
            "SELECT DISTINCT name FROM feature WHERE symbol=? AND timeframe=? ORDER BY name",
            (symbol, timeframe))
        return [r[0] for r in cur.fetchall()]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM feature").fetchone()[0]

    def close(self) -> None:
        self.conn.close()


def materialize_indicators(bars: list[Bar], store: FeatureStore,
                           specs: list[dict]) -> int:
    """Calcule chaque indicateur (specs YAML : name + params) et l'écrit dans le store.

    spec = {"name": "rsi", "params": {"period": 14}, "as": "rsi_14"}
    """
    if not bars:
        return 0
    symbol, tf = bars[0].instrument, bars[0].timeframe
    ts = [b.ts for b in bars]
    written = 0
    for spec in specs:
        ind = indicators.create(spec["name"], **spec.get("params", {}))
        series = ind.compute(bars)
        feat_name = spec.get("as", spec["name"])
        written += store.write(symbol, tf, feat_name, list(zip(ts, series)))
    return written


def _iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()
