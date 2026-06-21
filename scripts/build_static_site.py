#!/usr/bin/env python3
"""Construit le SITE STATIQUE = vrai front Next.js (parité `make start`) + données figées (JSON) +
notes d'analyse HTML → dossier `site/` (déployable sur GitHub Pages).

Étapes : dump des payloads API en JSON → export statique Next.js → copie vers site/.
Pré-requis : Node + dépendances web installées (`cd apps/web && npm ci`). Pour un aperçu léger
sans Node, utiliser `scripts/build_site.py` (terminal autonome).

  NEXT_PUBLIC_BASE_PATH=/Screening-Trading python scripts/build_static_site.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
SITE = ROOT / "site"
BP = os.environ.get("NEXT_PUBLIC_BASE_PATH", "")
MAX_REPORTS = os.environ.get("QUANT_MAX_REPORTS", "120")


def main() -> int:
    # 1) fige les données + notes
    print("→ [1/3] Dump des données API + notes HTML…")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "dump_static.py"),
                        "--max-reports", MAX_REPORTS], cwd=str(ROOT))
    if r.returncode != 0:
        print("⛔ dump_static a échoué — données absentes : on n'expose pas un site cassé "
              "(toutes les pages tourneraient en boucle). Corrige le snapshot puis relance.")
        return 1

    # 2) export statique Next.js (même UI que make start)
    print("→ [2/3] Export statique Next.js…")
    env = {**os.environ, "STATIC_EXPORT": "1", "NEXT_PUBLIC_STATIC": "1", "NEXT_PUBLIC_BASE_PATH": BP}
    b = subprocess.run(["npm", "run", "build"], cwd=str(WEB), env=env)
    if b.returncode != 0:
        print("⛔ build Next.js échoué."); return 1

    # 3) copie out/ → site/
    print("→ [3/3] Assemblage site/…")
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(WEB / "out", SITE)
    (SITE / ".nojekyll").write_text("")
    print(f"✅ site/ prêt ({sum(1 for _ in SITE.rglob('*'))} fichiers). Base path: '{BP or '(racine)'}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
