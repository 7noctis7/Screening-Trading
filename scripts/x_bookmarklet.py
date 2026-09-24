#!/usr/bin/env python3
"""Transforme `tools/x_export.js` en marque-page cliquable (`javascript:…`).

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
SOURCE = RACINE / "tools" / "x_export.js"


def bookmarklet(js: str) -> str:
    """`javascript:` + encodage d'URL. Aucune minification : le code reste lisible."""
    return "javascript:" + quote(js, safe="")


def main() -> int:
    if not SOURCE.exists():
        print(f"introuvable : {SOURCE}", file=sys.stderr)
        return 1
    lien = bookmarklet(SOURCE.read_text(encoding="utf-8"))
    print("MARQUE-PAGE — copier la ligne ci-dessous comme ADRESSE d'un favori.")
    print("Puis : ouvrir un profil X, faire défiler, cliquer le favori.\n")
    print(lien)
    print(f"\n({len(lien)} caractères — les navigateurs acceptent bien au-delà.)")
    print("\nVariante sans favori : coller le contenu de tools/x_export.js dans la")
    print("console du navigateur (F12 → Console).")
    print("\nLe fichier x_posts.jsonl atterrit dans vos téléchargements. Ensuite :")
    print("    mv ~/Downloads/x_posts.jsonl data/x_posts.jsonl && make x-ingest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
