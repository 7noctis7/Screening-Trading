#!/usr/bin/env python3
"""Ingère des publications X dans le store, depuis une source enregistrée.

    make x-ingest                      # source « fichier », data/x_posts.jsonl
    make x-ingest ARGS="--source fichier --chemin /tmp/export.jsonl"
    make x-ingest ARGS="--etat"        # ce que le store contient, sans rien écrire

Le format attendu est une ligne JSON par publication. Deux champs sont obligatoires —
le compte et l'horodatage — parce que sans eux une publication ne se trie ni ne se
trace. Tout le reste est facultatif et sera pré-rempli par `extraction`, qui rend
`UNKNOWN`/`None` dès qu'elle hésite plutôt qu'une étiquette plausible :

    {"id": "1", "compte": "astekz", "ts": "2026-09-24T10:00:00Z",
     "texte": "BTCUSDT long TP1 65000"}

Les lignes illisibles sont COMPTÉES et rapportées, jamais devinées ni tues.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.social.sources import charger_plugins, sources  # noqa: E402
from packages.social.store import StorePublications, chemin_db  # noqa: E402


def _etat(db: str) -> int:
    store = StorePublications(db)
    try:
        print(f"Base      : {db}")
        print(f"Stock     : {store.compter()} publication(s)")
        comptes = store.comptes()
        print(f"Comptes   : {', '.join(comptes) if comptes else '(aucun)'}")
        syms = store.symboles()
        print(f"Symboles  : {', '.join(syms) if syms else '(aucun)'}")
    finally:
        store.close()
    return 0


def main() -> int:
    disponibles = charger_plugins()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="fichier", choices=disponibles)
    ap.add_argument("--chemin", default=None, help="pour la source « fichier »")
    ap.add_argument("--db", default=None)
    ap.add_argument("--etat", action="store_true", help="n'écrit rien")
    a = ap.parse_args()

    db = a.db or chemin_db()
    if a.etat:
        return _etat(db)

    src = sources.create(a.source, **({"chemin": a.chemin} if a.chemin else {}))
    lues = src.lire()
    rejets = list(getattr(src, "rejets", []))

    if not lues and not rejets:
        print(f"Aucune publication lue par la source « {a.source} ».")
        print("Le flux reste NON CONNECTÉ — l'onglet le dira, il n'inventera rien.")
        return 0

    store = StorePublications(db)
    try:
        avant = store.compter()
        ecrites = store.ecrire(lues)
        apres = store.compter()
    finally:
        store.close()

    print(f"Lues      : {ecrites}")
    print(f"Nouvelles : {apres - avant}   "
          "(le reste existait déjà — écriture idempotente)")
    print(f"Stock     : {apres}")
    if rejets:
        print(f"\n{len(rejets)} ligne(s) IGNORÉE(S), jamais devinée(s) :")
        for r in rejets[:10]:
            print(f"  · {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
