#!/usr/bin/env python3
"""make certification — un module dit-il la vérité sur sa place dans le système ?

Deux questions, deux gravités :
  · INCOHÉRENCE  un module se déclare hors production et y est atteignable → BLOQUANT.
  · DETTE        un module se déclare hors production et l'est → à trancher (brancher
                 ou supprimer), mais ce n'est pas un défaut : on le compte.

  make certification
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from packages.common.certification import _modules, inventaire
    inv = inventaire(ROOT)
    mods = _modules(ROOT)
    print(f"\nCertification · {inv['n_shadow']} module(s) déclarés SHADOW\n")
    for m in inv["shadow"]:
        n = len(mods[m].read_text(encoding="utf-8", errors="ignore").splitlines())
        etat = "❌ ATTEIGNABLE EN PROD" if m in inv["incoherences"] else "dette"
        print(f"  {m:<44} {n:>5} l.  {etat}")
    print(f"\n  dette de câblage : {inv['dette_lignes']} ligne(s) jamais exécutées")
    if inv["incoherences"]:
        print("\n  → ❌ un module ment sur son statut : il se déclare hors production")
        print("       et y est atteignable. Corriger le STATUT ou couper le lien.")
        return 1
    print("  → ✅ aucun module ne ment sur son statut.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
