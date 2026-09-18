#!/usr/bin/env python3
"""Refuse de régénérer le verrou depuis une machine qui n'entraîne pas.

CE QUI S'EST PASSÉ (18/09). `make verrou-regen` annonce depuis toujours « à lancer SUR
LA MACHINE QUI ENTRAÎNE » — et ne vérifiait rien. Lancé sur le Mac (Darwin/arm64,
Python 3.12), il a produit un `constraints.txt` de **140 paquets** qui a remplacé celui
du VPS (Linux/x86_64, Python 3.14, **159 paquets**) : plus de roues CUDA, et des
épinglages résolus pour une autre version de Python.

POURQUOI C'EST LE PIRE CAS. `make verrou` restait VERT des deux côtés — les sept
bibliothèques d'entraînement étaient épinglées ici comme là-bas. Rien n'invitait donc à
regarder, et le verrou aurait cessé de décrire la machine qui produit les modèles sans
qu'aucun voyant ne change. Un avertissement dans une phrase d'aide n'est pas un
garde-fou : il ne s'exécute pas.

CE QUE CETTE GARDE N'EST PAS. Un blocage sur une absence. Sans entraînement tracé au
registre, on ne SAIT pas quelle machine entraîne : le script le dit et laisse passer.
Et `QUANT_VERROU_FORCE=1` reste la porte de sortie — un garde-fou qu'on ne peut pas
contourner devient un jour le problème.

  python scripts/verrou_regen_garde.py      (ou : make verrou-regen, qui l'appelle)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    from packages.mlops.environnement import (
        environnement,
        machine_compatible,
        machine_de_reference,
    )
    reference = machine_de_reference()
    verdict, motif = machine_compatible(reference)
    ici = environnement()
    signature = f"{ici.get('os')} · {ici.get('machine')} · Python {ici.get('python')}"

    if verdict is True:
        print(f"  ✓ {motif}\n    ici : {signature}")
        return 0
    if verdict is None:
        print(f"  · {motif}\n    ici : {signature}")
        return 0

    print(f"\n  ✗ CETTE MACHINE N'EST PAS CELLE QUI ENTRAÎNE — {motif}")
    print(f"    ici                  : {signature}")
    print(f"    dernier entraînement : {reference['os']} · {reference['machine']} · "
          f"Python {reference['python']}  ({reference['version']})")
    print("\n  Un verrou résolu ailleurs n'épingle pas ce que la machine")
    print("  d'entraînement installera : roues de plateforme absentes, versions")
    print("  résolues pour une autre mineure de Python. Et `make verrou` resterait")
    print("  VERT — c'est pour ça que la vérification est ici, pas dans une phrase.")
    print("\n  À faire : relancer `make verrou-regen` SUR la machine d'entraînement.")
    print("  Si c'est bien ici que l'entraînement doit se faire désormais :")
    print("      QUANT_VERROU_FORCE=1 make verrou-regen\n")
    return 1


if __name__ == "__main__":
    if os.environ.get("QUANT_VERROU_FORCE"):
        print("  ⚠ QUANT_VERROU_FORCE=1 — vérification de machine CONTOURNÉE.")
        raise SystemExit(0)
    raise SystemExit(main())
