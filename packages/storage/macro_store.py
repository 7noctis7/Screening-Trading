"""MacroStore — observations macro VINTAGE, requête point-in-time (anti-fuite).

Stocke (series, obs_date, value, realtime_start). `as_of(series, t)` ne retourne que
ce qui était CONNU à `t` :
  1. on ne garde que les vintages publiés (realtime_start <= t) — respecte le délai
     de publication (une donnée du mois M n'est connue qu'en M+1) ;
  2. par période observée, on prend la DERNIÈRE révision connue à `t` ;
  3. on renvoie la période la plus récente (obs_date max) disponible à `t`.

C'est la logique ALFRED. Entraîner un ML sans ça = fuite massive du futur.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.core.models import MacroObservation

_DDL = """
CREATE TABLE IF NOT EXISTS macro_obs (
    series_id TEXT NOT NULL, obs_date TEXT NOT NULL,
    value REAL NOT NULL, realtime_start TEXT NOT NULL,
    PRIMARY KEY (series_id, obs_date, realtime_start)
);
CREATE INDEX IF NOT EXISTS idx_macro ON macro_obs(series_id, realtime_start);
"""


class MacroStore:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(_DDL)
        self.conn.commit()

    def upsert(self, obs: list[MacroObservation]) -> int:
        rows = [(o.series_id, _iso(o.obs_date), o.value, _iso(o.realtime_start))
                for o in obs]
        self.conn.executemany(
            "INSERT OR REPLACE INTO macro_obs VALUES (?,?,?,?)", rows)
        self.conn.commit()
        return len(rows)

    def as_of(self, series_id: str, t: datetime) -> tuple[datetime, float] | None:
        """Valeur de la période la plus récente, telle que CONNUE à `t`."""
        ti = _iso(t)
        cur = self.conn.execute(
            "SELECT obs_date, value FROM macro_obs "
            "WHERE series_id=? AND realtime_start<=? "
            "AND realtime_start = ("                       # dernière révision connue à t
            "  SELECT MAX(realtime_start) FROM macro_obs m2 "
            "  WHERE m2.series_id=macro_obs.series_id AND m2.obs_date=macro_obs.obs_date "
            "  AND m2.realtime_start<=?) "
            "ORDER BY obs_date DESC LIMIT 1",
            (series_id, ti, ti))
        r = cur.fetchone()
        return (datetime.fromisoformat(r[0]), r[1]) if r else None

    def history_as_of(self, series_id: str, t: datetime) -> list[tuple[datetime, float]]:
        """Toute la série telle que connue à `t` (pour calculer tendances point-in-time)."""
        ti = _iso(t)
        cur = self.conn.execute(
            "SELECT obs_date, value FROM macro_obs "
            "WHERE series_id=? AND realtime_start<=? "
            "AND realtime_start = ("
            "  SELECT MAX(realtime_start) FROM macro_obs m2 "
            "  WHERE m2.series_id=macro_obs.series_id AND m2.obs_date=macro_obs.obs_date "
            "  AND m2.realtime_start<=?) "
            "ORDER BY obs_date", (series_id, ti, ti))
        return [(datetime.fromisoformat(r[0]), r[1]) for r in cur.fetchall()]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM macro_obs").fetchone()[0]

    def close(self) -> None:
        self.conn.close()


def _iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()
