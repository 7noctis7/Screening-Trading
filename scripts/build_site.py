#!/usr/bin/env python3
"""Assemble le site statique (PWA) pour GitHub Pages → dossier `site/`.

Génère le terminal autonome (`interactive.html`) à partir du snapshot (données RÉELLES si
`data/market.db` est présent, sinon synthétique de démo), puis copie les fichiers PWA dans `site/`
avec un `index.html` (page d'accueil). Aucune dépendance au Mac : conçu pour tourner dans GitHub
Actions. Best-effort : ne casse jamais (un site est toujours produit)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "apps" / "web" / "preview"
SITE = ROOT / "site"


def main() -> int:
    # 1) génère interactive.html (+ manifest + sw.js) via le générateur existant
    r = subprocess.run([sys.executable, str(PREVIEW / "build_interactive.py")], cwd=str(ROOT))
    if r.returncode != 0:
        print("⚠️ build_interactive a échoué — on tente d'assembler ce qui existe.")

    SITE.mkdir(exist_ok=True)
    html = PREVIEW / "interactive.html"
    if not html.exists():
        print("⛔ interactive.html introuvable — abandon."); return 1
    # 2) copie les artefacts PWA + crée index.html (point d'entrée Pages)
    shutil.copy2(html, SITE / "interactive.html")
    shutil.copy2(html, SITE / "index.html")
    for f in ("manifest.webmanifest", "sw.js"):
        src = PREVIEW / f
        if src.exists():
            shutil.copy2(src, SITE / f)
    # 3) .nojekyll (sinon GitHub Pages ignore certains fichiers)
    (SITE / ".nojekyll").write_text("")
    print(f"✅ site prêt : {SITE} ({', '.join(p.name for p in SITE.iterdir())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
