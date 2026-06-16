"""Audit trail — journal append-only et REJOUABLE de chaque décision/ordre.

Chaque entrée : horodatage + type + contexte (features, régime, version de modèle…).
Permet de rejouer une décision avec son contexte exact (traçabilité, conformité).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, kind TEXT NOT NULL, context TEXT NOT NULL
);
"""


class AuditTrail:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(_DDL)
        self.conn.commit()

    def record(self, kind: str, context: dict, ts: datetime | None = None) -> int:
        ts = ts or datetime.now(timezone.utc)
        cur = self.conn.execute(
            "INSERT INTO audit(ts, kind, context) VALUES (?,?,?)",
            (ts.isoformat(), kind, json.dumps(context, default=str)))
        self.conn.commit()
        return cur.lastrowid

    def query(self, kind: str | None = None) -> list[dict]:
        sql = "SELECT ts, kind, context FROM audit"
        params: tuple = ()
        if kind:
            sql += " WHERE kind=?"; params = (kind,)
        sql += " ORDER BY id"
        return [{"ts": r[0], "kind": r[1], "context": json.loads(r[2])}
                for r in self.conn.execute(sql, params).fetchall()]

    def replay(self):
        """Itère les entrées dans l'ordre (rejeu de la séquence de décisions)."""
        yield from self.query()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
