#!/usr/bin/env python3
"""Ingestion des titres DÉLISTÉS → data/delisted.csv (corrige le biais du survivant).

Heuristique libre et point-in-time : un symbole présent dans la base de prix dont la DERNIÈRE
barre est antérieure de plus de `--stale-days` à aujourd'hui est considéré sorti de cote / halté.
Aucune source payante, aucune fuite future. Best-effort : ne crashe jamais le pipeline.

Exemples :
    python scripts/ingest_delisted.py                  # market.db + crypto.db, seuil 60 j
    python scripts/ingest_delisted.py --stale-days 90 --db data/market.db
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.data.survivorship import derive_delisted, write_delisted  # noqa: E402


def _last_bars(db: str) -> dict[str, str]:
    """Dernière date de barre par symbole, via le moteur de lecture (repli SQLite)."""
    try:
        from packages.data.engine import read_prices_rows
    except Exception:  # noqa: BLE001
        return {}
    last: dict[str, str] = {}
    for r in read_prices_rows(db):
        s, ts = r.get("symbol"), r.get("ts")
        if s and ts and (s not in last or str(ts) > last[s]):
            last[s] = str(ts)[:10]
    return last


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingestion des titres délistés (anti-biais du survivant)")
    ap.add_argument("--db", action="append", help="base(s) de prix (défaut : market.db + crypto.db)")
    ap.add_argument("--stale-days", type=int, default=60, help="ancienneté max avant délisting présumé")
    ap.add_argument("--dry-run", action="store_true", help="affiche sans écrire")
    args = ap.parse_args()

    dbs = args.db or ["data/market.db", "data/crypto.db"]
    last_all: dict[str, str] = {}
    for db in dbs:
        last_all.update(_last_bars(db))
    if not last_all:
        print("aucune base de prix lisible — rien à faire (déposez data/market.db).")
        return 0

    rows = derive_delisted(last_all, asof=date.today(), stale_days=args.stale_days)
    print(f"{len(rows)} titre(s) délisté(s) détecté(s) sur {len(last_all)} (seuil {args.stale_days} j).")
    for r in rows[:20]:
        print(f"  {r['symbol']:<8} dernière barre {r['delisted_on']}")
    if args.dry_run:
        print("(dry-run : aucune écriture)")
        return 0
    total = write_delisted(rows)
    print(f"data/delisted.csv : {total} titre(s) au total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
