#!/usr/bin/env python3
"""Passe à « absent » les open/high/low nuls des bases de prix (cf. packages/data/prix_absents).

  python scripts/reparer_prix_absents.py              # data/market.db + data/crypto.db
  python scripts/reparer_prix_absents.py --dbs ~/Desktop/YAHOO.db

Idempotent : un second passage ne modifie rien. Une base absente est ignorée. Lancé dans
le build Pages AVANT l'audit, car le cache HuggingFace porte encore les zéros tant qu'il
n'est pas repoussé depuis une base réparée (`make hf-push`, décision du propriétaire).
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.data import prix_absents  # noqa: E402
from packages.data.engine import _resolve_db  # noqa: E402


def reparer_base(chemin: Path) -> dict[str, int] | None:
    """Répare la table `prices` d'une base ; None si la base ou la table n'existe pas."""
    if not chemin.exists():
        return None
    conn = sqlite3.connect(chemin, timeout=120)
    try:
        conn.execute("PRAGMA busy_timeout=120000")
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='prices'"
                            ).fetchone():
            return None
        n = prix_absents.reparer(conn)
        assert prix_absents.compter(conn) == 0, "réparation incomplète"
        return n
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dbs", nargs="*", default=["market", "crypto"])
    a = ap.parse_args(argv)
    for db in a.dbs:
        chemin = _resolve_db(db)
        n = reparer_base(chemin)
        if n is None:
            print(f"· {chemin.name} : absente ou sans table prices — ignorée")
        else:
            print(f"· {chemin.name} : {sum(n.values())} valeur(s) passée(s) à « absent » {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
