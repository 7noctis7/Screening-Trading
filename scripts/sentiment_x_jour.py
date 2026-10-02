"""Écrit le score du jour dans data/social_x.db, après l'ingestion des comptes.

Ne contacte pas X. Ne classe que les messages déjà en base. Sans message, la
journée reste vide : on n'invente pas un top 20.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from packages.social.sentiment_jour import enregistrer
from packages.social.store import StorePublications, chemin_db


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    jour = args[0] if args else datetime.now(timezone.utc).date().isoformat()
    store = StorePublications(chemin_db())
    try:
        n = enregistrer(store.conn, store.toutes(), jour)
    finally:
        store.close()
    print(f"sentiment_jour {jour} : {n} actif(s) cités dans les comptes suivis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
