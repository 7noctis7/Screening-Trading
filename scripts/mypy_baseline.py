#!/usr/bin/env python3
"""Gate mypy « aucune NOUVELLE erreur » — bloquant en CI, sans exiger de solder la dette d'abord.

  python scripts/mypy_baseline.py            # échoue si une erreur absente de la référence apparaît
  python scripts/mypy_baseline.py --update   # réécrit la référence (après avoir corrigé des erreurs)

POURQUOI (31/10). L'étape mypy de la CI tournait en `continue-on-error` : 2 917 erreurs, donc
une de plus ne se voyait pas. Rendre mypy bloquant tel quel aurait cassé chaque PR ; le laisser
informatif laissait la dette grossir sans bruit. La référence fige l'existant et ne laisse
passer que ce qui ne l'aggrave pas.

La clé d'une erreur est (fichier, code, message) SANS numéro de ligne : ajouter une ligne en
tête de fichier décale toutes les erreurs suivantes, et une clé qui contiendrait la ligne les
déclarerait toutes « nouvelles ». On compte les occurrences : deux erreurs identiques dans le
même fichier sont deux erreurs, et en ajouter une troisième doit échouer.

La référence n'est valable que pour la version de mypy qui l'a produite (une autre version
trouve d'autres erreurs) : elle est épinglée dans `.github/workflows/ci.yml` et notée ici.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "config" / "mypy_baseline.json"
CIBLE = "packages"

# `packages/x.py:12: error: Message  [code]` — les lignes `note:` ne sont pas des erreurs.
_LIGNE = re.compile(r"^(?P<fichier>[^:\n]+\.pyi?):(?P<ligne>\d+): error: (?P<msg>.*?)"
                    r"(?:  \[(?P<code>[a-z0-9-]+)\])?$")
# Un message qui cite une autre ligne (« already defined on line 45 ») bougerait avec elle.
_REF_LIGNE = re.compile(r"\bline \d+\b")


def cle(fichier: str, code: str, msg: str) -> str:
    """Clé stable d'une erreur : indépendante de sa ligne et des lignes qu'elle cite."""
    return f"{fichier.replace(chr(92), '/')}::{code or '-'}::{_REF_LIGNE.sub('line N', msg)}"


def lire_sortie(sortie: str) -> tuple[Counter[str], dict[str, list[str]]]:
    """Compte les erreurs par clé et garde les lignes brutes (pour montrer OÙ est le nouveau)."""
    compte: Counter[str] = Counter()
    brutes: dict[str, list[str]] = {}
    for ligne in sortie.splitlines():
        m = _LIGNE.match(ligne.strip())
        if not m:
            continue
        k = cle(m["fichier"], m["code"] or "", m["msg"])
        compte[k] += 1
        brutes.setdefault(k, []).append(ligne.strip())
    return compte, brutes


def comparer(actuel: Counter[str], reference: Counter[str]) -> tuple[Counter[str], Counter[str]]:
    """(nouvelles, corrigées) — chacune en nombre d'occurrences par clé."""
    nouvelles = Counter({k: n - reference.get(k, 0) for k, n in actuel.items()
                         if n > reference.get(k, 0)})
    corrigees = Counter({k: n - actuel.get(k, 0) for k, n in reference.items()
                         if n > actuel.get(k, 0)})
    return nouvelles, corrigees


def lancer_mypy() -> tuple[str, str]:
    """Sortie de mypy sur la cible, et sa version. Pas de shell : liste d'arguments."""
    version = subprocess.run([sys.executable, "-m", "mypy", "--version"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split()[1]
    res = subprocess.run([sys.executable, "-m", "mypy", CIBLE], cwd=ROOT,
                         capture_output=True, text=True)
    if res.returncode not in (0, 1):  # 2 = mypy lui-même a échoué (config, crash)
        raise SystemExit(f"⛔ mypy n'a pas pu s'exécuter (code {res.returncode}) :\n"
                         f"{res.stdout}{res.stderr}")
    return res.stdout, version


def charger_reference(chemin: Path) -> tuple[Counter[str], str | None]:
    if not chemin.exists():
        return Counter(), None
    doc = json.loads(chemin.read_text(encoding="utf-8"))
    return Counter(doc["erreurs"]), doc.get("mypy")


def ecrire_reference(chemin: Path, compte: Counter[str], version: str) -> None:
    doc = {"mypy": version, "cible": CIBLE, "total": sum(compte.values()),
           "erreurs": dict(sorted(compte.items()))}
    chemin.write_text(json.dumps(doc, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")


def rapport(nouvelles: Counter[str], corrigees: Counter[str],
            brutes: dict[str, list[str]], total: int, total_ref: int) -> int:
    """Affiche le verdict ; renvoie le code de sortie (1 si au moins une erreur nouvelle)."""
    print(f"mypy {CIBLE} : {total} erreur(s) · référence {total_ref}")
    if corrigees:
        print(f"✓ {sum(corrigees.values())} erreur(s) de la référence ont disparu — "
              f"`python scripts/mypy_baseline.py --update` pour resserrer la référence.")
    if not nouvelles:
        print("✓ Aucune erreur nouvelle.")
        return 0
    print(f"\n⛔ {sum(nouvelles.values())} erreur(s) NOUVELLE(S) par rapport à la référence :")
    for k in sorted(nouvelles):
        for ligne in brutes.get(k, [k])[-nouvelles[k]:]:
            print(f"   {ligne}")
    print("\nCorriger ces erreurs. Si elles sont voulues (ex. un fichier DÉPLACÉ garde ses "
          "erreurs sous un autre nom), régénérer : python scripts/mypy_baseline.py --update")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--update", action="store_true", help="réécrire la référence")
    a = ap.parse_args(argv)
    sortie, version = lancer_mypy()
    actuel, brutes = lire_sortie(sortie)
    if a.update:
        ecrire_reference(REFERENCE, actuel, version)
        print(f"✓ Référence écrite : {sum(actuel.values())} erreur(s), mypy {version} "
              f"→ {REFERENCE.relative_to(ROOT)}")
        return 0
    reference, version_ref = charger_reference(REFERENCE)
    if version_ref and version_ref != version:
        print(f"⚠ Référence produite par mypy {version_ref}, exécution avec mypy {version} : "
              f"les écarts peuvent venir de la version, pas du code.")
    nouvelles, corrigees = comparer(actuel, reference)
    return rapport(nouvelles, corrigees, brutes, sum(actuel.values()), sum(reference.values()))


if __name__ == "__main__":
    sys.exit(main())
