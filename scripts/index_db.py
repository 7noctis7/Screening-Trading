"""Crée les INDEX sur la base de prix (YAHOO.db) — à lancer UNE fois, gros gain de vitesse.

Sans index sur la clé étrangère, chaque lecture d'un actif scanne toute la table P_1D
(des millions de lignes) → très lent. Cet outil crée un index (id_price_ticker, timestamp)
sur chaque table de prix. Sûr : `CREATE INDEX IF NOT EXISTS` (idempotent), ne modifie aucune
donnée. Peut prendre 1–3 min sur 4 Go, une seule fois.

  python3 scripts/index_db.py
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_DATE = ["date", "datetime", "timestamp", "dt", "ts", "time", "day", "period"]
_LINK = ["ticker_id", "tickerid", "sec_id", "secid", "instrument_id", "id", "ticker", "symbol", "code"]
_CLOSE = ["close", "adj_close", "adjclose", "adj", "last", "price", "c"]


def _pick(cols, cands):
    for c in cands:
        if c in cols:
            return cols[c]
    for c in cands:
        for k, orig in cols.items():
            if c in k:
                return orig
    return None


def main() -> None:
    from scripts.check_db import _find_db
    db = _find_db()
    if db is None:
        print("❌ Base introuvable (QUANT_PRICE_DB ou ~/Desktop/YAHOO.db).")
        return
    print(f"Base : {db}")
    conn = sqlite3.connect(db)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    done = 0
    for t in tables:
        cols = {c[1].lower(): c[1] for c in conn.execute(f'PRAGMA table_info("{t}")')}
        dat, link, cls = _pick(cols, _DATE), _pick(cols, _LINK), _pick(cols, _CLOSE)
        if not (dat and link and cls):
            continue                       # pas une table de prix
        name = f"ix_{t}_{link}_{dat}".replace("-", "_")
        print(f"  Index sur {t}({link}, {dat}) … ", end="", flush=True)
        t0 = time.time()
        conn.execute(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{t}"("{link}","{dat}")')
        conn.commit()
        print(f"OK ({time.time() - t0:.1f}s)")
        done += 1
    conn.close()
    print(f"Terminé : {done} index créés/présents. Les lectures du robot sont maintenant rapides.")


if __name__ == "__main__":
    main()
