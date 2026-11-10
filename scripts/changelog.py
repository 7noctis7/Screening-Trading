#!/usr/bin/env python3
"""Génère CHANGELOG.md depuis l'historique de `main` : une ligne par PR fusionnée, par mois.

  python scripts/changelog.py              # écrit CHANGELOG.md (depuis origin/main ou main)
  python scripts/changelog.py --stdout     # affiche sans écrire

Le journal du vault raconte le POURQUOI ; ce fichier liste le QUOI, vérifiable PR par PR.
Il se régénère, il ne s'édite pas à la main. La version vient de `pyproject.toml`.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_PR = re.compile(r"\(#(\d+)\)\s*$")
_MERGE = re.compile(r"^Merge pull request #(\d+) from \S+")
_BRUIT = ("chore: keepalive",)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


def _branche() -> str:
    for ref in ("origin/main", "main"):
        if subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=ROOT,
                          capture_output=True).returncode == 0:
            return ref
    raise SystemExit("ni origin/main ni main : rien à lire")


def entrees(ref: str) -> list[tuple[str, str, int]]:
    """(date, titre, n° de PR) des commits de premier parent qui viennent d'une PR."""
    out = []
    brut = _git("log", ref, "--first-parent", "--format=%cs%x1f%s%x1f%b%x1e")
    for bloc in brut.split("\x1e"):
        if not bloc.strip():
            continue
        date, sujet, corps = (bloc.strip("\n").split("\x1f") + ["", ""])[:3]
        if sujet.startswith(_BRUIT):
            continue
        if m := _MERGE.match(sujet):        # merge classique : le titre est la 1re ligne du corps
            titre = next((l.strip() for l in corps.splitlines() if l.strip()), sujet)
            out.append((date, titre, int(m[1])))
        elif m := _PR.search(sujet):        # squash : « Titre (#123) »
            out.append((date, _PR.sub("", sujet).strip(), int(m[1])))
    return out


def rendre(lignes: list[tuple[str, str, int]], version: str, date: str) -> str:
    mois: OrderedDict[str, list[str]] = OrderedDict()
    for d, titre, n in lignes:
        mois.setdefault(d[:7], []).append(f"- {titre} (#{n})")
    corps = "\n\n".join(f"### {m}\n\n" + "\n".join(items) for m, items in mois.items())
    return (f"# Changelog\n\n> Généré par `make changelog` depuis l'historique de `main` "
            f"(une ligne par PR fusionnée,\n> la plus récente en tête). Ne pas éditer à la main : "
            f"le POURQUOI est dans `vault/04_JOURNAL.md`.\n\n"
            f"## [{version}] — {date}\n\n{corps}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args(argv)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    ref = _branche()
    lignes = entrees(ref)
    texte = rendre(lignes, version, lignes[0][0] if lignes else "")
    if a.stdout:
        print(texte)
    else:
        (ROOT / "CHANGELOG.md").write_text(texte, encoding="utf-8")
        print(f"✓ CHANGELOG.md : {len(lignes)} PR, version {version} ({ref})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
