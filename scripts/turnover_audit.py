#!/usr/bin/env python3
"""Coût réel du rebalancement quotidien — mesure avant décision.

  python scripts/turnover_audit.py

Lit `data/journal.db`. Si vide (conteneur cloud fraîchement cloné, ou avant le
premier `make journal-pull`), le dit clairement au lieu d'inventer un chiffre.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from packages.research.turnover_audit import rapport_complet
    from packages.storage import SqliteTradeJournal

    db = ROOT / "data" / "journal.db"
    if not db.exists():
        print("UNCALIBRATED — data/journal.db introuvable. "
              "Lance `make journal-pull` (si HF_TOKEN configuré) ou exécute ce "
              "script sur la machine qui détient le vrai journal (Mac mini / VPS).")
        return
    trades = SqliteTradeJournal(str(db)).all(legacy=False)
    print(rapport_complet(trades))


if __name__ == "__main__":
    main()
