#!/usr/bin/env python3
"""Transforme un script d'export en marque-page cliquable (`javascript:…`).

    make x-export                  # profils X
    make x-export ARGS=--discord   # salons Discord

Le script d'export vit en clair dans le dépôt — lisible, commenté, révisable. Le
marque-page n'en est qu'un emballage, GÉNÉRÉ à la demande : coller une version figée
dans la documentation la ferait diverger du code au premier correctif, et personne ne
s'en apercevrait avant de constater un export cassé.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

RACINE = Path(__file__).resolve().parents[1]
SCRIPTS = {"x": RACINE / "tools" / "x_export.js",
           "discord": RACINE / "tools" / "discord_export.js"}
OU = {"x": "un profil X", "discord": "un salon Discord"}


def bookmarklet(js: str) -> str:
    """`javascript:` + encodage d'URL. Aucune minification : le code reste lisible."""
    return "javascript:" + quote(js, safe="")


def main() -> int:
    quoi = "discord" if "--discord" in sys.argv else "x"
    source = SCRIPTS[quoi]
    if not source.exists():
        print(f"introuvable : {source}", file=sys.stderr)
        return 1
    lien = bookmarklet(source.read_text(encoding="utf-8"))
    print("MARQUE-PAGE — copier la ligne ci-dessous comme ADRESSE d'un favori.")
    print(f"Puis : ouvrir {OU[quoi]}, faire défiler, cliquer le favori.\n")
    print(lien)
    print(f"\n({len(lien)} caractères — les navigateurs acceptent bien au-delà.)")
    print(f"\nVariante sans favori : coller le contenu de {source.relative_to(RACINE)}")
    print("dans la console du navigateur (F12 → Console).")
    if quoi == "discord":
        print("\nDiscord ne rend que la zone VISIBLE : l'export capture ce que vous")
        print("avez fait défiler. Remonter puis réexporter complète le fichier — les")
        print("identifiants étant stables, la réingestion ne duplique rien.")
    print("\nLe fichier x_posts.jsonl atterrit dans vos téléchargements. Ensuite :")
    print("    mv ~/Downloads/x_posts.jsonl data/x_posts.jsonl && make x-ingest")
    print("\nL'autre marque-page : make x-export ARGS="
          + ("" if quoi == "discord" else "--discord"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
