"""Ingestion des PRIX CRYPTO réels (top-N par market cap) → data/crypto.db.

La crypto n'est PAS dans YAHOO.db (actions only) → la poche Bitmart tournait en synthétique
(donc écartée). Ce script récupère l'OHLCV réel via yfinance (BTC-USD, ETH-USD, …) pour les
cryptos de ton univers et l'écrit dans une base SIDECAR `data/crypto.db` (format long, lue en
plus de YAHOO.db). Résultat : sleeve crypto, cœur crypto, graphes & comparaison sur du RÉEL.

On n'écrit JAMAIS dans YAHOO.db (4 Go, lecture seule) → base dédiée, non destructive.

  python scripts/ingest_crypto.py            # top 50 cryptos
  python scripts/ingest_crypto.py --top 100
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=50, help="nb de cryptos (par ordre de l'univers = cap)")
    ap.add_argument("--days", type=int, default=3650, help="profondeur d'historique (jours)")
    a = ap.parse_args()

    from apps.api.snapshot import _seed_universe, datetime, timedelta, timezone
    inst = [m for m in _seed_universe() if m.get("asset_class") == "crypto"]
    bases: list[str] = []
    for m in inst:                                       # bases uniques, dans l'ordre de l'univers
        # normalise vers la base : BTC/USDT → BTC, BTC-USD → BTC, BTC → BTC (évite le suffixe ajouté
        # en double « BTC-USD-USD » quand l'univers stocke déjà le format yfinance).
        raw = m["symbol"].upper().split("/")[0]
        base = raw[:-4] if raw.endswith("-USD") else (raw[:-5] if raw.endswith("-USDT") else raw)
        if base and base not in bases:
            bases.append(base)
    bases = bases[:a.top]
    if not bases:
        print("Aucune crypto dans l'univers (data/seed/crypto_*.csv)."); return
    print(f"{len(bases)} cryptos à ingérer (yfinance) : {', '.join(bases[:15])}…\n")

    try:
        import yfinance as yf
    except Exception:  # noqa: BLE001
        print("yfinance indisponible — uv pip install yfinance."); return

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=a.days)
    db = ROOT / "data" / "crypto.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")          # lecteurs API + écriture sans 'database is locked'
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("CREATE TABLE IF NOT EXISTS prices (symbol TEXT, date TEXT, open REAL, high REAL, "
                 "low REAL, close REAL, volume REAL, PRIMARY KEY (symbol, date))")
    ok = 0
    for i, base in enumerate(bases, 1):
        ysym = f"{base}-USD"
        try:
            df = yf.Ticker(ysym).history(start=start.date().isoformat(), end=end.date().isoformat())
            if df is None or len(df) < 250:
                continue
            rows = [(ysym, d.date().isoformat(), float(r.Open), float(r.High), float(r.Low),
                     float(r.Close), float(r.Volume or 0))
                    for d, r in df.iterrows() if r.Close == r.Close and r.Close > 0]
            if rows:
                conn.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)", rows)
                conn.commit()
                ok += 1
        except Exception:  # noqa: BLE001
            continue
        if i % 10 == 0:
            print(f"  … {i}/{len(bases)} ({ok} avec données)")
    conn.close()
    if ok == 0:
        print("Aucune donnée crypto récupérée (réseau ?)."); return
    print(f"\n✅ {ok} cryptos écrites → {db}")
    print("   Relance le site (make api) : sleeve crypto, cœur crypto, graphes & comparaison sont")
    print("   maintenant sur des prix RÉELS. Backtest cœur crypto : make crypto-core.")


if __name__ == "__main__":
    main()
