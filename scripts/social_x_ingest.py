#!/usr/bin/env python3
"""Ingère des publications X dans le store, depuis une source enregistrée.

    make x-ingest                      # source « fichier », data/x_posts.jsonl
    make x-ingest ARGS="--source rss"       # flux RSS listés dans QUANT_X_RSS
    make x-ingest ARGS="--source telegram"  # canaux listés dans QUANT_TG_CANAUX
    make x-ingest ARGS="--source discord"   # salons listés dans QUANT_DISCORD_SALONS
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
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.common.env import load_env  # noqa: E402
from packages.social.sources import (  # noqa: E402
    charger_plugins,
    est_configuree,
    sources,
)
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


def _arguments(disponibles: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="fichier", choices=disponibles)
    ap.add_argument("--chemin", default=None, help="source « fichier » : le JSONL")
    ap.add_argument("--flux", default=None,
                    help="source « rss » : URL séparées par des virgules")
    ap.add_argument("--canaux", default=None,
                    help="source « telegram » : « canal[:compte] », par virgules")
    ap.add_argument("--salons", default=None,
                    help="source « discord » : « id[:compte] », par virgules")
    ap.add_argument("--db", default=None)
    ap.add_argument("--etat", action="store_true", help="n'écrit rien")
    ap.add_argument("--garder", type=int,
                    default=int(os.environ.get("QUANT_SOCIAL_GARDER") or 50),
                    help="publications gardées PAR COMPTE (0 = tout garder)")
    ap.add_argument("--si-configuree", action="store_true",
                    help="sort en silence (code 0) si la source n'a rien à lire — "
                         "ce que la chaîne quotidienne utilise pour ne pas remplir "
                         "son journal d'échecs attendus")
    return ap.parse_args()


def _ecrire(db: str, lues: list, garder: int) -> tuple[int, int, int, int]:
    """Écrit, applique le plafond, et rend (lues, nouvelles, retirées, stock)."""
    store = StorePublications(db)
    try:
        avant = store.ids()
        ecrites = store.ecrire(lues)
        retirees = store.garder_recentes(garder)
        # Compter les nouvelles APRÈS le plafond : un message plus ancien que les
        # `garder` plus récents rentrerait puis ressortirait aussitôt, et « Nouvelles »
        # l'annoncerait à chaque passage alors qu'il n'est jamais resté.
        nouvelles = len(store.ids() - avant)
        return ecrites, nouvelles, retirees, store.compter()
    finally:
        store.close()


def main() -> int:
    # `.env` est la SEULE configuration que l'utilisateur écrit. Sans ce chargement, le
    # script marchait depuis un shell où les variables avaient été exportées à la main,
    # et nulle part ailleurs — en particulier pas sous cron, dont l'env est nu.
    load_env()
    a = _arguments(charger_plugins())
    db = a.db or chemin_db()
    if a.etat:
        return _etat(db)

    # Chaque plugin a ses propres options : les lui passer TOUTES ferait tomber la
    # commande sur un TypeError au lieu de l'ignorer. On ne transmet que la sienne.
    options = {"fichier": {"chemin": a.chemin}, "rss": {"flux": a.flux},
               "telegram": {"canaux": a.canaux}, "discord": {"salons": a.salons}}
    kwargs = {k: v for k, v in options.get(a.source, {}).items() if v}
    src = sources.create(a.source, **kwargs)
    if a.si_configuree and not est_configuree(src):
        return 0
    lues = src.lire()
    rejets = list(getattr(src, "rejets", []))

    if not lues and not rejets:
        print(f"Aucune publication lue par la source « {a.source} ».")
        print("Le flux reste NON CONNECTÉ — l'onglet le dira, il n'inventera rien.")
        return 0

    ecrites, nouvelles, retirees, stock = _ecrire(db, lues, a.garder)
    print(f"Lues      : {ecrites}")
    print(f"Nouvelles : {nouvelles}   "
          "(le reste existait déjà — écriture idempotente)")
    # TOUJOURS une ligne, même à zéro : sans elle, un plafond actif qui n'a rien eu à
    # retirer et un plafond désactivé s'écrivaient pareil dans le journal du cron — on
    # ne pouvait plus voir une garde qui ne tourne jamais. Relevé en revue de #409.
    if a.garder > 0:
        print(f"Retirées  : {retirees}   (au-delà des {a.garder} plus récentes "
              "par compte)")
    else:
        print("Retirées  : —   (rétention DÉSACTIVÉE, --garder 0 : tout est gardé)")
    print(f"Stock     : {stock}")
    if rejets:
        print(f"\n{len(rejets)} ligne(s) IGNORÉE(S), jamais devinée(s) :")
        for r in rejets[:10]:
            print(f"  · {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
