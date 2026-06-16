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
        self._norm = None       # (price_table, link_col, datecol, {ohlc}, {SYMBOLE->id})
        self._per_ticker = set()
        self._detect(table)

    def _columns(self, table: str) -> dict:
        cur = self._conn.execute(f'PRAGMA table_info("{table}")')
        return {r[1].lower(): r[1] for r in cur.fetchall()}

    _LINK = ["ticker_id", "tickerid", "sec_id", "secid", "instrument_id", "id",
             "ticker", "symbol", "code"]
    _META_ID = ["id", "ticker_id", "tickerid", "sec_id", "secid", "rowid"]
    _DAILY_HINTS = ("1d", "_d", "daily", "eod", "day")

    def _detect(self, table: str | None) -> None:
        tables = [r[0] for r in self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        # 1) format LONG : une table avec colonne symbole + date + close
        for t in ([table] if table else tables):
            if not t:
                continue
            cl = self._columns(t)
            if _pick(cl, _SYM) and _pick(cl, _DATE) and _pick(cl, _OHLC["close"]):
                self._long = (t, _pick(cl, _SYM), _pick(cl, _DATE),
                              {k: _pick(cl, v) for k, v in _OHLC.items()})
                return
        # 2) format NORMALISÉ : table de prix (date+close+lien) + table méta (symbole→id)
        price = []
        for t in tables:
            cl = self._columns(t)
            dat, cls = _pick(cl, _DATE), _pick(cl, _OHLC["close"])
            if dat and cls:
                price.append((t, cl, dat, _pick(cl, self._LINK)))
        price = [p for p in price if p[3]]
        if price:
            price.sort(key=lambda p: (any(h in p[0].lower() for h in self._DAILY_HINTS),
                                      self._count(p[0])), reverse=True)
            pt, cl, dat, link = price[0]
            sym2id = self._symbol_map(tables, pt)
            if sym2id is not None or link.lower() in ("ticker", "symbol", "code"):
                self._norm = (pt, link, dat, {k: _pick(cl, v) for k, v in _OHLC.items()},
                              sym2id or {})
                return
        self._per_ticker = set(tables)     # sinon : suppose une table par ticker

    def _count(self, table: str) -> int:
        try:
            return self._conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        except sqlite3.Error:
            return 0

    def _symbol_map(self, tables, price_table) -> dict | None:
        """Construit SYMBOLE(maj) → identifiant depuis une table méta (Ticker/symbols…)."""
        for t in tables:
            if t == price_table:
                continue
            cl = self._columns(t)
            sym = _pick(cl, _SYM)
            idc = _pick(cl, self._META_ID) or "rowid"
            if not sym:
                continue
            try:
                rows = self._conn.execute(f'SELECT "{idc}","{sym}" FROM "{t}"').fetchall()
            except sqlite3.Error:
                continue
            m = {str(r[1]).upper(): r[0] for r in rows if r[1] is not None}
            if m:
                return m
        return None

    @property
    def schema(self) -> str:
        if self._long:
            return f"long:{self._long[0]}"
        if self._norm:
            return f"normalisé:{self._norm[0]} (lien {self._norm[1]}, {len(self._norm[4])} tickers)"
        return f"per-ticker({len(self._per_ticker)} tables)"

    def _link_value(self, symbol: str):
        if not self._norm:
            return None
        pt, link, _, _, sym2id = self._norm
        if sym2id:
            return sym2id.get(symbol.upper())
        return symbol            # le lien EST déjà le symbole

    def supports(self, symbol: str) -> bool:
        if self._long:
            t, sym, _, _ = self._long
            return self._conn.execute(
                f'SELECT 1 FROM "{t}" WHERE "{sym}"=? LIMIT 1', (symbol,)).fetchone() is not None
        if self._norm:
            return self._link_value(symbol) is not None
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
            elif self._norm:
                pt, link, dat, o, _ = self._norm
                lv = self._link_value(symbol)
                if lv is None:
                    return []
                q = (f'SELECT {self._select(dat, o)} FROM "{pt}" WHERE "{link}"=? '
                     f'AND "{dat}">=? AND "{dat}"<=? ORDER BY "{dat}"')
                rows = self._conn.execute(q, (lv, s, e)).fetchall()
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
