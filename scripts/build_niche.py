"""Inspecte la YAHOO.db et construit un niche.csv à partir des tickers RÉELLEMENT présents.

  export QUANT_PRICE_DB=$HOME/Desktop/YAHOO.db

  python scripts/build_niche.py                          # liste : classes/secteurs + comptes
  python scripts/build_niche.py --class equity --sector "Information Technology" --limit 40 \
         --out data/niche_real.csv                       # écrit une niche réelle

Puis : QUANT_UNIVERSE=data/niche_real.csv make screen-niche
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspecte la base et construit une niche réelle")
    ap.add_argument("--class", dest="cls", default=None, help="filtre classe (equity/etf/crypto/forex/commodity/index)")
    ap.add_argument("--sector", default=None, help="filtre secteur (sous-chaîne, insensible à la casse)")
    ap.add_argument("--limit", type=int, default=40, help="nb max de tickers dans la niche")
    ap.add_argument("--out", default=None, help="fichier de sortie (ex. data/niche_real.csv)")
    a = ap.parse_args()

    from apps.api.snapshot import _db_full_universe
    uni = _db_full_universe()
    if not uni:
        print("⛔ Base introuvable. Fais : export QUANT_PRICE_DB=\"$HOME/Desktop/YAHOO.db\"")
        return

    if not a.out:                                      # mode LISTE
        by_cls = Counter(r["asset_class"] for r in uni)
        print(f"YAHOO.db — {len(uni)} tickers\n\nPar classe d'actifs :")
        for cls, n in by_cls.most_common():
            print(f"  {cls:10s} {n:>6d}")
        eq = [r for r in uni if r["asset_class"] == "equity" and r.get("sector")]
        by_sec = Counter(r["sector"] for r in eq)
        print("\nActions — top secteurs :")
        for sec, n in by_sec.most_common(15):
            print(f"  {sec:34s} {n:>5d}")
        print("\n→ Construis une niche : python scripts/build_niche.py --class equity "
              "--sector \"<secteur>\" --limit 40 --out data/niche_real.csv")
        return

    # mode ÉCRITURE : filtre + échantillon
    rows = uni
    if a.cls:
        rows = [r for r in rows if r["asset_class"] == a.cls.lower()]
    if a.sector:
        rows = [r for r in rows if a.sector.lower() in (r.get("sector") or "").lower()]
    rows = rows[: a.limit]
    if len(rows) < 5:
        print(f"⚠️ Seulement {len(rows)} tickers correspondent — élargis le filtre (niche trop étroite).")
        if not rows:
            return
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "name", "asset_class", "venue", "currency", "sector"])
        for r in rows:
            w.writerow([r["symbol"], r.get("name", ""), r["asset_class"],
                        r.get("venue", ""), r.get("currency", ""), r.get("sector", "")])
    print(f"✅ {len(rows)} tickers RÉELS écrits → {out}")
    print(f"   Screene-la : QUANT_UNIVERSE={a.out} make screen-niche")


if __name__ == "__main__":
    main()
