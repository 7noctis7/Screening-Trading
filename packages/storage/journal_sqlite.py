"""Journal de trades PERSISTANT — SQLite (stdlib, testable offline). Remplace le v1 in-memory.

Même interface que `TradeJournal` (append/all/pnls/to_csv) → interchangeable dans le moteur.
- DB dédiée `data/journal.db` (JAMAIS mélangée au cache prix régénérable *.db).
- `features_snapshot` sérialisé en JSON TEXT → réapprentissage ML sans perte (le dict figé
  à la DÉCISION est stocké tel quel ; aucune reconstruction a posteriori = anti-fuite).
- **Idempotence** : PRIMARY KEY (id) + UPSERT → réimport/retry sûrs, zéro doublon.
- Colonne `legacy` REQUÊTABLE : les calibrations filtrent `WHERE legacy=0` (fills importés = 1).
- Migration auto du schéma au 1er lancement (CREATE TABLE IF NOT EXISTS).
"""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.core.models import AssetClass, Side, TradeRecord

_log = logging.getLogger(__name__)

DEFAULT_DB = "data/journal.db"

_DDL = """
CREATE TABLE IF NOT EXISTS trades (
    id                TEXT PRIMARY KEY,
    instrument        TEXT NOT NULL,
    asset_class       TEXT NOT NULL,
    venue             TEXT NOT NULL,
    side              TEXT NOT NULL,
    qty               REAL NOT NULL,
    entry_ts          TEXT NOT NULL,      -- ISO 8601
    entry_price       REAL NOT NULL,
    avg_price         REAL NOT NULL,
    exit_ts           TEXT,
    exit_price        REAL,
    fees              REAL DEFAULT 0,
    slippage          REAL DEFAULT 0,
    entry_reason      TEXT DEFAULT '',
    exit_reason       TEXT DEFAULT '',
    regime            TEXT,
    strategy          TEXT,
    features_snapshot TEXT DEFAULT '{}',  -- JSON du dict figé à la décision
    pnl_gross         REAL,
    pnl_net           REAL,
    pnl_pct           REAL,
    r_multiple        REAL,
    is_win            INTEGER,
    duration_s        REAL,
    mfe               REAL,
    mae               REAL,
    legacy            INTEGER NOT NULL DEFAULT 0,  -- 1 = fill importé (features non capturées)
    ingested_at       TEXT NOT NULL       -- lineage
);
CREATE INDEX IF NOT EXISTS idx_trades_legacy ON trades(legacy);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);
"""

_COLS = [
    "id", "instrument", "asset_class", "venue", "side", "qty", "entry_ts",
    "entry_price", "avg_price", "exit_ts", "exit_price", "fees", "slippage",
    "entry_reason", "exit_reason", "regime", "strategy", "features_snapshot",
    "pnl_gross", "pnl_net", "pnl_pct", "r_multiple", "is_win", "duration_s",
    "mfe", "mae", "legacy", "ingested_at",
]


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


class SqliteTradeJournal:
    """Journal persistant. Interface identique à `TradeJournal` (drop-in)."""

    def __init__(self, db_path: str | Path = DEFAULT_DB) -> None:
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(_DDL)          # migration auto
        self.conn.commit()

    def append(self, trade: TradeRecord, *, legacy: bool = False) -> None:
        """UPSERT idempotent sur `id`. `legacy=True` pour un fill importé sans features.

        Warning explicite si un trade LIVE (legacy=False) arrive sans features_snapshot :
        signale une perte de capture ML sans planter le flux d'exécution.
        """
        if not legacy and not trade.features_snapshot:
            _log.warning(
                "TradeRecord %s (%s) enregistré SANS features_snapshot — "
                "capture ML perdue (attendu depuis la couche décision).",
                trade.id, trade.instrument)
        row = self._to_row(trade, legacy)
        placeholders = ",".join("?" for _ in _COLS)
        updates = ",".join(f"{c}=excluded.{c}" for c in _COLS if c != "id")
        self.conn.execute(
            f"INSERT INTO trades ({','.join(_COLS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            row)
        self.conn.commit()

    def all(self, *, legacy: bool | None = None) -> list[TradeRecord]:
        """Tous les trades (ordre d'insertion). `legacy=False` pour la calibration."""
        q = f"SELECT {','.join(_COLS)} FROM trades"
        params: list = []
        if legacy is not None:
            q += " WHERE legacy=?"
            params.append(1 if legacy else 0)
        q += " ORDER BY rowid"
        cur = self.conn.execute(q, params)
        return [self._from_row(r) for r in cur.fetchall()]

    def pnls(self, *, legacy: bool | None = None) -> list[float]:
        return [t.pnl_net for t in self.all(legacy=legacy) if t.pnl_net is not None]

    def to_csv(self, path: str | Path) -> None:
        trades = self.all()
        if not trades:
            return
        fields = ["id", "instrument", "side", "strategy", "regime", "entry_ts",
                  "entry_price", "exit_ts", "exit_price", "qty", "pnl_net",
                  "pnl_pct", "r_multiple", "is_win", "entry_reason", "exit_reason"]
        with Path(path).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for t in trades:
                w.writerow({
                    "id": t.id, "instrument": t.instrument, "side": t.side.value,
                    "strategy": t.strategy, "regime": t.regime,
                    "entry_ts": t.entry_ts.isoformat(), "entry_price": round(t.entry_price, 4),
                    "exit_ts": t.exit_ts.isoformat() if t.exit_ts else "",
                    "exit_price": round(t.exit_price, 4) if t.exit_price else "",
                    "qty": round(t.qty, 6), "pnl_net": round(t.pnl_net or 0, 2),
                    "pnl_pct": round(t.pnl_pct or 0, 4), "r_multiple": round(t.r_multiple or 0, 2),
                    "is_win": t.is_win, "entry_reason": t.entry_reason,
                    "exit_reason": t.exit_reason})

    def close(self) -> None:
        self.conn.close()

    # -- (dé)sérialisation -------------------------------------------------
    @staticmethod
    def _to_row(t: TradeRecord, legacy: bool) -> tuple:
        return (
            t.id, t.instrument, t.asset_class.value, t.venue, t.side.value, t.qty,
            _iso(t.entry_ts), t.entry_price, t.avg_price, _iso(t.exit_ts), t.exit_price,
            t.fees, t.slippage, t.entry_reason, t.exit_reason, t.regime, t.strategy,
            json.dumps(t.features_snapshot, sort_keys=True), t.pnl_gross, t.pnl_net,
            t.pnl_pct, t.r_multiple,
            None if t.is_win is None else int(t.is_win),
            t.duration_s, t.mfe, t.mae, 1 if legacy else 0,
            datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _from_row(r: tuple) -> TradeRecord:
        d = dict(zip(_COLS, r))
        return TradeRecord(
            id=d["id"], instrument=d["instrument"],
            asset_class=AssetClass(d["asset_class"]), venue=d["venue"],
            side=Side(d["side"]), qty=d["qty"],
            entry_ts=datetime.fromisoformat(d["entry_ts"]),
            entry_price=d["entry_price"], avg_price=d["avg_price"],
            exit_ts=datetime.fromisoformat(d["exit_ts"]) if d["exit_ts"] else None,
            exit_price=d["exit_price"], fees=d["fees"], slippage=d["slippage"],
            entry_reason=d["entry_reason"], exit_reason=d["exit_reason"],
            regime=d["regime"], strategy=d["strategy"],
            features_snapshot=json.loads(d["features_snapshot"] or "{}"),
            pnl_gross=d["pnl_gross"], pnl_net=d["pnl_net"], pnl_pct=d["pnl_pct"],
            r_multiple=d["r_multiple"],
            is_win=None if d["is_win"] is None else bool(d["is_win"]),
            duration_s=d["duration_s"], mfe=d["mfe"], mae=d["mae"])
