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


def _universe() -> list[tuple[str, str]]:
    from apps.api.snapshot import _seed_universe
    return [(m["symbol"], m.get("asset_class", "equity")) for m in _seed_universe()]


def _ysym(sym: str, ac: str) -> str | None:
    """Ticker au format Yahoo (None = à ignorer ici). Crypto → géré par ingest_crypto (crypto.db)."""
    from apps.api.snapshot import _yahoo_aliases
    if ac == "crypto":
        return None                                  # crypto = base dédiée (make ingest-crypto)
    if ac in ("equity", "etf", ""):
        return sym
    for a in _yahoo_aliases(sym, ac):                # forex/indice/commodité → alias Yahoo (=X, ^, =F)
        if a.startswith("^") or a.endswith(("=X", "=F", "-USD")):
            return a
    return sym


def _connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=60)           # attend le verrou (lecteurs API) au lieu d'échouer
    conn.execute("PRAGMA journal_mode=WAL")          # lecteurs + 1 écrivain en parallèle (pas de lock)
    conn.execute("PRAGMA busy_timeout=60000")        # 60 s d'attente si la base est occupée
    conn.executescript(_DDL)
    return conn


def _last_date(conn, symbol: str) -> str | None:
    r = conn.execute("SELECT MAX(date) FROM prices WHERE symbol=?", (symbol,)).fetchone()
    return r[0] if r and r[0] else None


def _fetch_yf(symbol: str, start: str, end: str, ysym: str | None = None) -> list[tuple]:
    """Bougies réelles via Ticker.history (colonnes simples, robuste — évite le multi-index de
    yf.download qui cassait l'extraction). `symbol` = clé stockée ; `ysym` = ticker Yahoo interrogé."""
    import yfinance as yf
    df = yf.Ticker(ysym or symbol).history(start=start, end=end, auto_adjust=False)
    if df is None or df.empty:
        return []

    def g(row, k):
        v = row.get(k)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return v if v == v else None                 # NaN → None

    out = []
    for ts, row in df.iterrows():
        out.append((symbol, ts.strftime("%Y-%m-%d"), g(row, "Open"), g(row, "High"), g(row, "Low"),
                    g(row, "Close"), g(row, "Close"), g(row, "Volume")))
    return out


def ingest(symbols: list[tuple[str, str]], since: str, daily: bool) -> None:
    conn = _connect()
    end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    total, ok, fail, skip = 0, 0, 0, 0
    for i, (sym, ac) in enumerate(symbols, 1):
        ysym = _ysym(sym, ac)
        if ysym is None:                              # crypto → ignoré (make ingest-crypto)
            skip += 1
            continue
        start = since
        if daily:
            last = _last_date(conn, sym)
            if last:
                start = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                if start >= end:
                    continue
        try:
            rows = _fetch_yf(sym, start, end, ysym=ysym)
        except Exception as e:  # noqa: BLE001
            fail += 1
            if fail <= 20:
                print(f"[{i}/{len(symbols)}] {sym}: échec ({str(e)[:60]})")
            continue
        if rows:
            conn.executemany("INSERT OR IGNORE INTO prices VALUES(?,?,?,?,?,?,?,?)", rows)
            conn.commit()
            total += len(rows)
            ok += 1
        if i % 25 == 0:
            print(f"  … {i}/{len(symbols)} symboles, {ok} OK, {total} barres insérées")
    print(f"Terminé : {ok} OK · {fail} échecs · {skip} crypto ignorées · {total} barres → {DB}")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingestion de prix réels vers data/market.db")
    ap.add_argument("--symbols", nargs="*", help="liste de tickers (défaut: univers complet)")
    ap.add_argument("--since", default="2015-01-01", help="date de début du backfill")
    ap.add_argument("--daily", action="store_true", help="incrémental : reprend après la dernière barre")
    a = ap.parse_args()
    syms = [(s, "equity") for s in a.symbols] if a.symbols else _universe()
    print(f"Ingestion de {len(syms)} symboles (since={a.since}, daily={a.daily})…")
    ingest(syms, a.since, a.daily)
