"""Ontologie légère (style Palantir object-centric simplifié).

Entités : Instrument, Strategy, Regime, Trade.
Relations : trades_in, uses_strategy, in_regime.
Stocké en SQLite. Sert de grounding structuré pour réduire hallucinations et tokens.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_DEFAULT_ONTO_DB = "data/ontology.db"


class Ontology:
    def __init__(self, db_path: str | Path = _DEFAULT_ONTO_DB):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,  -- instrument | strategy | regime | trade
                name TEXT,
                props TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS relations (
                src TEXT,
                rel TEXT,
                dst TEXT,
                PRIMARY KEY (src, rel, dst)
            );
            """
        )
        self.conn.commit()

    def upsert_entity(self, eid: str, etype: str, name: str, props: dict | None = None):
        self.conn.execute(
            "INSERT OR REPLACE INTO entities (id, type, name, props) VALUES (?,?,?,?)",
            (eid, etype, name, json.dumps(props or {})),
        )
        self.conn.commit()

    def add_relation(self, src: str, rel: str, dst: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO relations (src, rel, dst) VALUES (?,?,?)",
            (src, rel, dst),
        )
        self.conn.commit()

    def index_from_journal(self, journal_path: str = "data/journal.db"):
        from packages.storage.journal_sqlite import SqliteTradeJournal
        j = SqliteTradeJournal(journal_path)
        for t in j.all():
            tid = f"trade:{t.id}"
            self.upsert_entity(tid, "trade", t.id, {"instrument": t.instrument, "strategy": t.strategy})
            if t.instrument:
                iid = f"instrument:{t.instrument}"
                self.upsert_entity(iid, "instrument", t.instrument)
                self.add_relation(tid, "trades_in", iid)
            if t.strategy:
                sid = f"strategy:{t.strategy}"
                self.upsert_entity(sid, "strategy", t.strategy)
                self.add_relation(tid, "uses_strategy", sid)
            if t.regime:
                rid = f"regime:{t.regime}"
                self.upsert_entity(rid, "regime", t.regime)
                self.add_relation(tid, "in_regime", rid)
        j.close()

    def neighbors(self, eid: str, rel: str | None = None) -> list[dict]:
        q = "SELECT dst, rel FROM relations WHERE src=?"
        params = [eid]
        if rel:
            q += " AND rel=?"
            params.append(rel)
        rows = self.conn.execute(q, params).fetchall()
        return [{"id": r[0], "rel": r[1]} for r in rows]

    def search_entities(self, query: str, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, type, name FROM entities WHERE name LIKE ? OR id LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [{"id": r[0], "type": r[1], "name": r[2]} for r in rows]

    def close(self):
        self.conn.close()
