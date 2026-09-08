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
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _bases_univers(top: int) -> list[str]:
    """Bases crypto uniques de l'univers, plafonnées à `top`, ordre du classement."""
    from apps.api.snapshot import _seed_universe
    inst = [m for m in _seed_universe() if m.get("asset_class") == "crypto"]
    bases: list[str] = []
    for m in inst:
        # normalise vers la base : BTC/USDT → BTC, BTC-USD → BTC, BTC → BTC (évite le suffixe
        # ajouté en double « BTC-USD-USD » quand l'univers stocke déjà le format yfinance).
        raw = m["symbol"].upper().split("/")[0]
        base = raw[:-4] if raw.endswith("-USD") else (raw[:-5] if raw.endswith("-USDT") else raw)
        if base and base not in bases:
            bases.append(base)
    return bases[:top]


# Certaines bases n'ont PAS le ticker Yahoo qu'on croit : le symbole court est occupé
# par un homonyme illiquide, et `{base}-USD` ramène alors la série d'un autre jeton —
# figée, ou pleine de sauts absurdes. Une entrée ici force le ticker à interroger.
# À NE REMPLIR QUE SUR MESURE : `python scripts/diag_source_crypto.py` confronte chaque
# série à une référence indépendante et imprime la ligne exacte à ajouter.
ALIAS_YAHOO: dict[str, str] = {}


def ticker_yahoo(base: str) -> str:
    """Ticker Yahoo à interroger pour cette base (override mesuré, sinon convention)."""
    return ALIAS_YAHOO.get(base.upper(), f"{base}-USD")


def _ingerer(conn: sqlite3.Connection, bases: list[str], start,
             end) -> tuple[int, list]:
    """Récupère chaque base via yfinance, écrit ce qui répond.

    Renvoie (nb réussi, échecs) où chaque échec est (base, ticker, cause). La première
    version renvoyait le seul compte des succès et avalait tout le reste en silence :
    une source cassée ne laissait AUCUNE trace, et c'est comme ça que cinq séries
    `/USDC` sont restées inexploitables sans que rien ne le signale. Un ingest qui ne
    dit pas ce qu'il n'a pas pu faire donne l'illusion d'un univers complet.
    """
    import yfinance as yf
    ok, echecs = 0, []
    for i, base in enumerate(bases, 1):
        ysym = ticker_yahoo(base)
        try:
            df = yf.Ticker(ysym).history(start=start.date().isoformat(),
                                         end=end.date().isoformat())
        except Exception as e:  # noqa: BLE001
            echecs.append((base, ysym, f"réseau/yfinance : {type(e).__name__}"))
            continue
        if df is None or len(df) < 250:
            n = 0 if df is None else len(df)
            echecs.append((base, ysym, f"historique trop court ({n} barres)"))
            continue
        rows = [(ysym, d.date().isoformat(), float(r.Open), float(r.High), float(r.Low),
                 float(r.Close), float(r.Volume or 0))
                for d, r in df.iterrows() if r.Close == r.Close and r.Close > 0]
        if not rows:
            echecs.append((base, ysym, "aucune clôture valide"))
            continue
        conn.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)", rows)
        conn.commit()
        ok += 1
        if i % 10 == 0:
            print(f"  … {i}/{len(bases)} ({ok} avec données)")
    return ok, echecs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=50, help="nb de cryptos (par ordre de l'univers = cap)")
    ap.add_argument("--days", type=int, default=3650, help="profondeur d'historique (jours)")
    a = ap.parse_args()

    bases = _bases_univers(a.top)
    if not bases:
        print("Aucune crypto dans l'univers (data/seed/crypto_*.csv)."); return
    print(f"{len(bases)} cryptos à ingérer (yfinance) : {', '.join(bases[:15])}…\n")

    try:
        import yfinance  # noqa: F401
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
    ok, echecs = _ingerer(conn, bases, start, end)
    conn.close()
    if echecs:
        print(f"\n⚠  {len(echecs)} base(s) sans données — l'univers n'est PAS complet :")
        for base, ysym, cause in echecs[:20]:
            print(f"     · {base:8s} (interrogé « {ysym} ») — {cause}")
        if len(echecs) > 20:
            print(f"     … et {len(echecs) - 20} autre(s)")
        print("   Une série absente vaut mieux qu'une série fausse, mais elle doit se voir.")
        print("   Confronter les séries écrites à une référence : make diag-source-crypto")
    if ok == 0:
        print("Aucune donnée crypto récupérée (réseau ?)."); return
    print(f"\n✅ {ok} cryptos écrites → {db}")
    print("   Relance le site (make api) : sleeve crypto, cœur crypto, graphes & comparaison sont")
    print("   maintenant sur des prix RÉELS. Backtest cœur crypto : make crypto-core.")


if __name__ == "__main__":
    main()
