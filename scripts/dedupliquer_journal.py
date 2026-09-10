#!/usr/bin/env python3
"""Retire les doublons créés par les scripts de réparation. SIMULATION PAR DÉFAUT.

    python scripts/dedupliquer_journal.py               # simule, n'écrit RIEN
    python scripts/dedupliquer_journal.py --appliquer   # écrit, après sauvegarde

Ne supprime une ligne suffixée `-R\\d+` que si la ligne de BASE existe ET que leur
économie est identique (quantité, prix, dates, sortie). Tout le reste est déclaré
ambigu et conservé : sur ce projet, deux réparations « évidentes » ont déjà fabriqué
des pertes. Une sauvegarde horodatée est écrite avant toute modification.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from packages.research.deduplication import doublons_suffixes, rapport  # noqa: E402
from packages.storage.journal_sqlite import DEFAULT_DB, SqliteTradeJournal  # noqa: E402


def _sauvegarde(chemin: Path) -> Path:
    horo = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    cible = chemin.with_suffix(f".avant-dedup-{horo}.db")
    shutil.copy2(chemin, cible)
    return cible


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--appliquer", action="store_true",
                    help="écrit réellement (défaut : simulation)")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="chemin du journal")
    a = ap.parse_args()

    chemin = Path(a.db)
    if not chemin.exists():
        print(f"✗ journal introuvable : {chemin}")
        return 1

    journal = SqliteTradeJournal(chemin)
    tous = journal.all(legacy=None) if _accepte_none(journal) else journal.all()
    d = doublons_suffixes(tous)
    print(rapport(d))

    if not d["supprimables"]:
        print("\nRien à appliquer.")
        return 0
    if not a.appliquer:
        print(f"\nSIMULATION — aucune écriture. {len(d['supprimables'])} ligne(s) "
              "seraient supprimées. Relancer avec --appliquer pour écrire.")
        return 0

    copie = _sauvegarde(chemin)
    print(f"\nSauvegarde : {copie}")
    marques = ",".join("?" for _ in d["supprimables"])
    with journal.conn:
        journal.conn.execute(f"DELETE FROM trades WHERE id IN ({marques})",
                             d["supprimables"])
    print(f"✓ {len(d['supprimables'])} doublon(s) supprimé(s). "
          f"Restauration : cp {copie} {chemin}")
    return 0


def _accepte_none(journal) -> bool:
    """`all(legacy=None)` (tout le journal) n'existe pas sur toutes les versions."""
    try:
        journal.all(legacy=None)
        return True
    except TypeError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
