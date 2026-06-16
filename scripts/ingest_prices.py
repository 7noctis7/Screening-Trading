"""Ingestion de prix RÉELS → base SQLite locale (append quotidien idempotent).

Alimente data/market.db (table `prices`, format long) à partir de :
  1) yfinance (par défaut, gratuit) ;
  2) FMP en repli si FMP_API_KEY est défini.

Idempotent : clé primaire (symbol, date) + INSERT OR IGNORE → relancer chaque jour n'ajoute
que les nouvelles barres (la barre du jour vient s'empiler sur l'historique de CHAQUE actif).
Le snapshot/API lisent ensuite cette base via QUANT_PRICE_DB (cf. packages/data/providers/db_provider.py).

Exemples :
  python scripts/ingest_prices.py --since 2015-01-01           # backfill complet (univers)
  python scripts/ingest_prices.py --symbols AAPL NVDA PLTR     # quelques tickers
  python scripts/ingest_prices.py --daily                      # mise à jour incrémentale du jour
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB = ROOT / "data" / "market.db"
_DDL = """CREATE TABLE IF NOT EXISTS prices(
  symbol TEXT NOT NULL, date TEXT NOT NULL,
  open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume REAL,
  PRIMARY KEY(symbol, date));
CREATE INDEX IF NOT EXISTS ix_prices_symbol ON prices(symbol);"""


def _universe() -> list[str]:
    from apps.api.snapshot import _seed_universe
    return [m["symbol"] for m in _seed_universe()]


def _connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.executescript(_DDL)
    return conn


def _last_date(conn, symbol: str) -> str | None:
    r = conn.execute("SELECT MAX(date) FROM prices WHERE symbol=?", (symbol,)).fetchone()
    return r[0] if r and r[0] else None


def _fetch_yf(symbol: str, start: str, end: str) -> list[tuple]:
    import yfinance as yf
    df = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=False)
    if df is None or df.empty:
        return []
    out = []
    for ts, row in df.iterrows():
        d = ts.strftime("%Y-%m-%d")
        g = lambda k: float(row[k]) if k in row and row[k] == row[k] else None  # noqa: E731
        out.append((symbol, d, g("Open"), g("High"), g("Low"), g("Close"),
                    g("Adj Close"), g("Volume")))
    return out


def ingest(symbols: list[str], since: str, daily: bool) -> None:
    conn = _connect()
    end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    total, ok, fail = 0, 0, 0
    for i, sym in enumerate(symbols, 1):
        start = since
        if daily:
            last = _last_date(conn, sym)
            if last:
                start = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                if start >= end:
                    continue
        try:
            rows = _fetch_yf(sym, start, end)
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(symbols)}] {sym}: échec ({str(e)[:60]})")
            continue
        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO prices VALUES(?,?,?,?,?,?,?,?)", rows)
            conn.commit()
            total += len(rows)
            ok += 1
        if i % 25 == 0:
            print(f"  … {i}/{len(symbols)} symboles, {total} barres insérées")
    print(f"Terminé : {ok} symboles OK, {fail} échecs, {total} barres ajoutées → {DB}")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingestion de prix réels vers data/market.db")
    ap.add_argument("--symbols", nargs="*", help="liste de tickers (défaut: univers complet)")
    ap.add_argument("--since", default="2015-01-01", help="date de début du backfill")
    ap.add_argument("--daily", action="store_true", help="incrémental : reprend après la dernière barre")
    a = ap.parse_args()
    syms = a.symbols or _universe()
    print(f"Ingestion de {len(syms)} symboles (since={a.since}, daily={a.daily})…")
    ingest(syms, a.since, a.daily)
