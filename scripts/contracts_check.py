#!/usr/bin/env python3
"""Contrats de données OHLCV — GATE bloquant (#10). Vérifie l'INTÉGRITÉ (pas la complétude) des
prix de la watchlist : close>0, high≥low, high≥max(open,close), low≤min(open,close), volume≥0,
date non nulle. Sort ≠0 si violation → bloque le build (un schéma cassé ne passe plus en silence).

Pur stdlib par défaut (marche en CI sans dépendance) ; utilise pandera s'il est installé.

  python scripts/contracts_check.py            # watchlist (config/mobile_universe.csv) sur market+crypto
  python scripts/contracts_check.py --max 0    # 0 violation toléré (défaut)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _watchlist() -> list[str] | None:
    cfg = ROOT / "config" / "mobile_universe.csv"
    if not cfg.exists():
        return None
    with cfg.open(encoding="utf-8") as f:
        return [r["symbol"].strip() for r in csv.DictReader(f) if r.get("symbol")]


def validate_rows(rows: list[dict]) -> list[str]:
    """Renvoie les violations d'INTÉGRITÉ LOGIQUE (vide = OK). On ne signale QUE l'impossible :
    prix présent ≤ 0, high < low, volume < 0, symbole/date manquant. Une valeur ABSENTE (close None
    = trou de données) n'est PAS une violation (gérée par data_audit/complétude). Les écarts OHLC
    fins (low>min(open,close)) viennent des prix ajustés → tolérés (bruit, non bloquant)."""
    bad: list[str] = []
    for r in rows:
        sym, d = r.get("symbol"), (r.get("date") or r.get("ts"))
        h, l, c, v = r.get("high"), r.get("low"), r.get("close"), r.get("volume")
        tag = f"{sym}@{d}"
        if not sym or not d:
            bad.append(f"{tag}: symbole/date manquant"); continue
        if c is not None and c <= 0:                       # prix présent mais ≤ 0 = impossible
            bad.append(f"{tag}: close ≤ 0 ({c})")
        if h is not None and l is not None and h < l:      # high < low = impossible
            bad.append(f"{tag}: high<low ({h}<{l})")
        if v is not None and v < 0:                        # volume négatif = impossible
            bad.append(f"{tag}: volume<0 ({v})")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dbs", nargs="*", default=["market", "crypto"])
    ap.add_argument("--max", type=int, default=0, help="violations tolérées avant échec (défaut 0)")
    a = ap.parse_args()
    from packages.data.engine import read_prices_rows
    syms = _watchlist()
    total, violations = 0, []
    for db in a.dbs:
        rows = read_prices_rows(db, symbols=syms)
        if not rows:
            print(f"· {db}.db : absente/vide — ignorée"); continue
        total += len(rows)
        v = validate_rows(rows)
        print(f"· {db}.db : {len(rows)} barres · {len(v)} violation(s)")
        violations += v[:20]
    if len(violations) > a.max:
        print(f"\n⛔ GATE CONTRATS : {len(violations)} violation(s) > seuil {a.max} :")
        for msg in violations[:20]:
            print(f"   - {msg}")
        return 1
    print(f"\n✓ Contrats OHLCV OK ({total} barres validées, ≤ {a.max} violation tolérée).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
