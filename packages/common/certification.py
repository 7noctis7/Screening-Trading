"""Cohérence entre le STATUT déclaré d'un module et sa place RÉELLE dans le système.

POURQUOI CE CONTRÔLE EXISTE. `vault/15_CERTIFICATION.md` pose la règle : « un composant
non certifié en prod = finding P0 ». Dix modules déclarent un `STATUT` SHADOW et
« Aucun appelant en production » — une affirmation vraie le jour où elle a été
écrite et que RIEN ne revérifie. Un import ajouté six semaines plus tard fait entrer en
production un module qui continue de jurer qu'il n'y est pas, et personne ne le voit.

CE QU'ON MESURE, ET SEULEMENT ÇA. L'atteignabilité par les imports, depuis les points
d'entrée de production, en fermeture transitive. C'est structurel, donc fiable. On ne
cherche PAS à deviner si un module « devrait » être branché : ce jugement est humain, il
appartient au TODO, pas à un linter.

DEUX SENS, DEUX GRAVITÉS. Un module SHADOW ATTEIGNABLE depuis la production est un
mensonge de certification — c'est le cas grave. Un module SHADOW inatteignable est un
inventaire à trancher : brancher ou supprimer. Le second est une dette, pas un défaut ;
on le compte, on ne le bloque pas.
"""

from __future__ import annotations

import re
from pathlib import Path

_STATUT = re.compile(r'^STATUT\s*=\s*["\']SHADOW', re.MULTILINE)
# `from packages.x.y import z` ET `import packages.x.y` : les deux formes du dépôt.
_IMPORT = re.compile(r"^\s*(?:from|import)\s+(packages(?:\.\w+)*)", re.MULTILINE)

POINTS_ENTREE_PROD = ("scripts/run_live.py", "apps/api/snapshot.py", "apps/api/main.py")


def _modules(racine: Path) -> dict[str, Path]:
    """{« packages.x.y »: chemin} pour tout le paquet, hors caches."""
    out: dict[str, Path] = {}
    for p in racine.glob("packages/**/*.py"):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(racine).with_suffix("")
        nom = ".".join(rel.parts)
        out[nom.removesuffix(".__init__")] = p
    return out


def _imports(chemin: Path) -> set[str]:
    texte = chemin.read_text(encoding="utf-8", errors="ignore")
    return set(_IMPORT.findall(texte))


def declarés_shadow(racine: str | Path) -> list[str]:
    """Modules déclarant `STATUT = "SHADOW…"`, triés."""
    racine = Path(racine)
    return sorted(nom for nom, p in _modules(racine).items()
                  if _STATUT.search(p.read_text(encoding="utf-8", errors="ignore")))


def atteignables(racine: str | Path,
                 entrees: tuple[str, ...] = POINTS_ENTREE_PROD) -> set[str]:
    """Fermeture transitive des modules `packages.*` atteints depuis les entrées.

    Un import absent du dépôt (dépendance externe) est ignoré : on ne suit que ce qu'on
    possède. Un import fait DANS une fonction compte autant qu'en tête de fichier — il
    s'exécute quand même, et le dépôt en use abondamment pour alléger les démarrages.
    """
    racine = Path(racine)
    connus = _modules(racine)
    a_voir: list[str] = []
    for e in entrees:
        p = racine / e
        if p.exists():
            a_voir.extend(_imports(p))
    vus: set[str] = set()
    while a_voir:
        m = a_voir.pop()
        if m in vus or m not in connus:
            continue
        vus.add(m)
        a_voir.extend(_imports(connus[m]))
    return vus


def incoherences(racine: str | Path,
                 entrees: tuple[str, ...] = POINTS_ENTREE_PROD) -> list[str]:
    """Modules qui se déclarent HORS production alors qu'ils y sont atteignables.

    C'est le seul cas BLOQUANT : le module ment sur son propre statut, et c'est
    exactement ce que le protocole de certification interdit.
    """
    joignables = atteignables(racine, entrees)
    return sorted(m for m in declarés_shadow(racine) if m in joignables)


def inventaire(racine: str | Path,
               entrees: tuple[str, ...] = POINTS_ENTREE_PROD) -> dict:
    """{shadow, atteignables_prod, incoherences, dette_lignes} — pour le rapport."""
    racine = Path(racine)
    shadow = declarés_shadow(racine)
    mods = _modules(racine)
    faux = incoherences(racine, entrees)
    dette = sum(len(mods[m].read_text(encoding="utf-8", errors="ignore").splitlines())
                for m in shadow if m not in faux)
    return {"shadow": shadow, "n_shadow": len(shadow), "incoherences": faux,
            "dette_lignes": dette, "ok": not faux}
