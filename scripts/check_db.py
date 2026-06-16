"""Diagnostic de connexion à votre base de prix (YAHOO.db) — à lancer SUR VOTRE MAC.

Vérifie que le projet voit et lit votre base, affiche le schéma détecté, des symboles
d'exemple, le nombre de barres et la plage de dates, puis confirme le MODE qu'utilisera
le terminal (réel / mixte / synthetic).

  python scripts/check_db.py
  python scripts/check_db.py --symbols AAPL NVDA PLTR BTC/USDC
  QUANT_PRICE_DB=~/Desktop/YAHOO.db python scripts/check_db.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Diagnostic YAHOO.db / base de prix")
    ap.add_argument("--symbols", nargs="*", default=["AAPL", "NVDA", "PLTR", "MSFT", "BTC/USDC"])
    a = ap.parse_args()

    from apps.api.snapshot import _price_db_path
    from packages.data.providers.db_provider import DBPriceProvider

    db = _price_db_path()
    if db is None:
        print("❌ Aucune base trouvée.")
        print("   → Placez YAHOO.db dans ~/Desktop/ OU exportez le chemin :")
        print("     export QUANT_PRICE_DB=/chemin/vers/YAHOO.db")
        return
    print(f"✅ Base détectée : {db}")
    size_mb = db.stat().st_size / 1e6
    print(f"   Taille : {size_mb:,.0f} Mo")
    try:
        prov = DBPriceProvider(db)
    except Exception as e:  # noqa: BLE001
        print(f"❌ Lecture impossible : {e}")
        return
    print(f"   Schéma détecté : {prov.schema}")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=4000)
    ok = 0
    for s in a.symbols:
        bars = prov.fetch_ohlcv(s, "1d", start, end)
        if bars:
            ok += 1
            print(f"   • {s:14s} {len(bars):>6d} barres  {bars[0].ts.date()} → {bars[-1].ts.date()}  "
                  f"dernier {bars[-1].close:.2f}")
        else:
            print(f"   • {s:14s} (absent de la base)")
    print(f"\n{ok}/{len(a.symbols)} symboles testés trouvés.")
    # mode effectif du terminal sur la fenêtre réelle (~4,6 ans)
    recent = end - timedelta(days=1700)
    found = sum(1 for s in a.symbols if len(prov.fetch_ohlcv(s, "1d", recent, end)) >= 250)
    if found == 0:
        print("⚠️  Aucun symbole testé n'a ≥250 barres récentes → le terminal resterait en "
              "'synthetic' pour ceux-ci. Vérifiez que la base couvre les ~5 dernières années.")
    else:
        print(f"➡️  Le terminal lira ces données en mode 'réel'/'mixte' (≥250 barres récentes "
              f"pour {found}/{len(a.symbols)}). Lancez : make api  ou  make interactive")


if __name__ == "__main__":
    main()
