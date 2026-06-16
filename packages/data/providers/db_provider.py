"""Provider OHLCV adossé à une BASE DE DONNÉES locale (SQLite, ex. YAHOO.db, ou DuckDB).

Permet d'utiliser une grande base historique (plusieurs Go) SANS la committer dans Git :
on pointe le chemin via la variable d'env QUANT_PRICE_DB (ou data/YAHOO.db). Le schéma est
auto-détecté :
  - format LONG : une table avec une colonne symbole + colonnes OHLC(V) + date ;
  - format PAR TICKER : une table par symbole (nom de table == ticker).
Lecture seule, robuste : un symbole introuvable renvoie [] (le snapshot retombe alors sur
le synthétique pour cet actif). Aucune dépendance hors stdlib (sqlite3) ; DuckDB si dispo.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.core.models import Bar

_OHLC = {"open": ["open", "o"], "high": ["high", "h"], "low": ["low", "l"],
         "close": ["close", "adj_close", "adjclose", "c"], "volume": ["volume", "vol", "v"]}
_DATE = ["date", "datetime", "timestamp", "ts", "day"]
_SYM = ["symbol", "ticker", "sym", "code"]


def _pick(cols_lower: dict, candidates: list[str]):
    for c in candidates:
        if c in cols_lower:
            return cols_lower[c]
    return None


class DBPriceProvider:
    name = "db"

    def __init__(self, path: str | Path, table: str | None = None) -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row
        self._long = None       # (table, symcol, datecol, {ohlc->col})
        self._per_ticker = set()
        self._detect(table)

    def _columns(self, table: str) -> dict:
        cur = self._conn.execute(f'PRAGMA table_info("{table}")')
        return {r[1].lower(): r[1] for r in cur.fetchall()}

    def _detect(self, table: str | None) -> None:
        tables = [r[0] for r in self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        cands = [table] if table else tables
        for t in cands:
            if not t:
                continue
            cl = self._columns(t)
            sym = _pick(cl, _SYM)
            dat = _pick(cl, _DATE)
            ohlc = {k: _pick(cl, v) for k, v in _OHLC.items()}
            if dat and ohlc["close"] and sym:
                self._long = (t, sym, dat, ohlc)
                return
        self._per_ticker = set(tables)     # sinon : suppose une table par ticker

    @property
    def schema(self) -> str:
        return f"long:{self._long[0]}" if self._long else f"per-ticker({len(self._per_ticker)} tables)"

    def supports(self, symbol: str) -> bool:
        if self._long:
            t, sym, _, _ = self._long
            r = self._conn.execute(
                f'SELECT 1 FROM "{t}" WHERE "{sym}"=? LIMIT 1', (symbol,)).fetchone()
            return r is not None
        return symbol in self._per_ticker

    @staticmethod
    def _select(dat, o) -> str:
        """SELECT date,open,high,low,close,volume avec NULL pour les colonnes absentes
        (positions fixes → construction de Bar robuste)."""
        col = lambda c: f'"{c}"' if c else "NULL"  # noqa: E731
        return (f'"{dat}",{col(o["open"])},{col(o["high"])},{col(o["low"])},'
                f'{col(o["close"])},{col(o["volume"])}')

    def fetch_ohlcv(self, symbol: str, timeframe: str, start: datetime,
                    end: datetime | None = None) -> list[Bar]:
        end = end or datetime.now(timezone.utc)
        s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        try:
            if self._long:
                t, sym, dat, o = self._long
                q = (f'SELECT {self._select(dat, o)} FROM "{t}" WHERE "{sym}"=? '
                     f'AND "{dat}">=? AND "{dat}"<=? ORDER BY "{dat}"')
                rows = self._conn.execute(q, (symbol, s, e)).fetchall()
            elif symbol in self._per_ticker:
                cl = self._columns(symbol)
                dat = _pick(cl, _DATE)
                o = {k: _pick(cl, v) for k, v in _OHLC.items()}
                if not (dat and o["close"]):
                    return []
                q = (f'SELECT {self._select(dat, o)} FROM "{symbol}" '
                     f'WHERE "{dat}">=? AND "{dat}"<=? ORDER BY "{dat}"')
                rows = self._conn.execute(q, (s, e)).fetchall()
            else:
                return []
        except sqlite3.Error:
            return []
        bars = []
        for r in rows:
            try:
                ts = _parse_ts(r[0])
                op = float(r[1] if r[1] is not None else r[4])
                hi = float(r[2] if r[2] is not None else r[4])
                lo = float(r[3] if r[3] is not None else r[4])
                cl_ = float(r[4])
                vol = float(r[5]) if len(r) > 5 and r[5] is not None else 0.0
                if cl_ > 0:
                    bars.append(Bar(symbol, timeframe, ts, op, hi, lo, cl_, vol))
            except (TypeError, ValueError):
                continue
        return bars


def _parse_ts(v) -> datetime:
    if isinstance(v, (int, float)):                 # epoch (s ou ms)
        sec = v / 1000 if v > 1e11 else v
        return datetime.fromtimestamp(sec, timezone.utc)
    s = str(v).replace("T", " ").strip()
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.fromisoformat(s[:19]).replace(tzinfo=timezone.utc)
