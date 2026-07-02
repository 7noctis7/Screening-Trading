#!/usr/bin/env python3
"""Import des fills Alpaca EXISTANTS dans le journal persistant (data/journal.db).

Ces fills sont antérieurs au câblage du journal : leurs features N'ONT JAMAIS été
capturées à la décision. On les importe donc avec `features_snapshot={}` et `legacy=1`.

INTERDIT ABSOLU : reconstruire les features a posteriori (RSI/ATR/... recalculés
aujourd'hui sur des barres postérieures = fuite look-ahead). Les fills legacy servent
au P&L/reporting, JAMAIS à la calibration ML (qui filtre `WHERE legacy=0`).

Idempotent : l'id est un hash déterministe des champs du fill → réimport = 0 doublon.
Dry-run par défaut ; `--commit` pour écrire.

Usage :
    python scripts/import_legacy_fills.py            # dry-run (montre ce qui serait importé)
    python scripts/import_legacy_fills.py --commit   # écrit dans data/journal.db
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.core.models import AssetClass, Side, TradeRecord  # noqa: E402
from packages.storage import SqliteTradeJournal  # noqa: E402


def _fill_id(fill: dict) -> str:
    """Id déterministe (idempotence) : hash des champs identifiant le fill."""
    key = f"{fill['symbol']}|{fill['side']}|{fill['qty']}|{fill['price']}|{fill['date']}"
    return "LEG-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def _to_record(fill: dict) -> TradeRecord | None:
    """Fill Alpaca (dict de broker.orders()) → TradeRecord legacy. None si inexploitable."""
    if not fill.get("date"):
        return None                                   # pas d'horodatage fiable → on n'invente pas
    try:
        ts = datetime.fromisoformat(fill["date"])
    except ValueError:
        return None
    side = Side.LONG if str(fill.get("side", "")).lower().startswith("buy") else Side.SHORT
    price = float(fill.get("price") or 0.0)
    qty = float(fill.get("qty") or 0.0)
    if qty <= 0 or price <= 0:
        return None
    return TradeRecord(
        id=_fill_id(fill), instrument=fill["symbol"], asset_class=AssetClass.EQUITY,
        venue="alpaca", side=side, qty=qty, entry_ts=ts, entry_price=price,
        avg_price=price, entry_reason="legacy_import", exit_reason="",
        features_snapshot={})                          # VIDE — jamais reconstruit


def main() -> int:
    ap = argparse.ArgumentParser(description="Import des fills Alpaca legacy → journal.")
    ap.add_argument("--limit", type=int, default=500, help="nb max de fills à lire")
    ap.add_argument("--db", default="data/journal.db", help="chemin du journal persistant")
    ap.add_argument("--commit", action="store_true", help="écrit (sinon dry-run)")
    args = ap.parse_args()

    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        fills = AlpacaBroker(paper=True).orders(limit=args.limit)
    except Exception as e:  # noqa: BLE001 — clés absentes / réseau / SDK
        print(f"[ERREUR] impossible de lire les fills Alpaca : {e}", file=sys.stderr)
        print("        (clés ALPACA_API_KEY / ALPACA_API_SECRET requises dans .env)")
        return 1

    records = [r for r in (_to_record(f) for f in fills) if r is not None]
    skipped = len(fills) - len(records)
    print(f"Fills lus : {len(fills)} · exploitables : {len(records)} · ignorés : {skipped}")

    if not args.commit:
        for r in records[:10]:
            print(f"  [dry-run] {r.id}  {r.instrument:6} {r.side.value:5} "
                  f"qty={r.qty:g} @ {r.entry_price:g}  {r.entry_ts.date()}  legacy=1")
        if len(records) > 10:
            print(f"  … (+{len(records) - 10} autres)")
        print("Dry-run : rien écrit. Relancer avec --commit pour importer.")
        return 0

    journal = SqliteTradeJournal(args.db)
    for r in records:
        journal.append(r, legacy=True)                 # idempotent (UPSERT sur id)
    total_legacy = len(journal.all(legacy=True))
    print(f"Importés : {len(records)} · total legacy en base : {total_legacy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
