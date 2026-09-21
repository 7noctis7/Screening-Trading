#!/usr/bin/env python3
"""Ce que `constraints.txt` NE couvre PAS pour l'entraînement.

  python scripts/verrou_env.py      (ou : make verrou)

Le verrou du dépôt est généré pour les extras `api`, `data` et `quant`. Il épingle donc
numpy, pandas et scipy — et laisse libres scikit-learn, xgboost, lightgbm et torch, c'est-
à-dire précisément ce qui entraîne. Un modèle sérialisé sous une version et rechargé sous
une autre peut se charger ET PRÉDIRE DIFFÉREMMENT, sans lever d'erreur.

Ce script ne régénère rien : la résolution télécharge les dépendances et doit tourner
sur la machine qui entraîne, pas dans un conteneur d'analyse. Il rend la commande
exacte —
et cette commande est une CIBLE du Makefile, jamais un binaire supposé présent.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    from packages.mlops.environnement import (
        applique,
        commande_regeneration,
        environnement,
        non_verrouillees,
        verrou,
    )
    fige = verrou()
    libres = non_verrouillees()
    env = environnement()
    print(f"\n  Verrou : {len(fige)} paquet(s) épinglé(s) dans constraints.txt")
    print(f"  Python courant : {env['python']} · {env['os']} · {env['machine']}")
    ok_applique, dit = applique()
    print(f"  {'✓' if ok_applique else '⚠'} {dit}")
    print("  " + "─" * 74)
    for lib in ("numpy", "pandas", "scipy", "scikit-learn", "xgboost", "lightgbm", "torch"):
        cle = lib.lower()
        etat = "épinglé " + fige[cle] if cle in fige else "LIBRE"
        installe = env.get(lib) or "absent"
        marque = " " if cle in fige else "⚠"
        print(f"  {marque} {lib:14s} {etat:22s} installé : {installe}")
    print("  " + "─" * 74)
    if libres:
        print(f"  ⚠ {len(libres)} bibliothèque(s) d'entraînement non épinglée(s) : "
              + ", ".join(libres))
        print("    Un run distant et un run local ne seront pas comparables.")
        print(f"\n    Régénérer SUR LA MACHINE QUI ENTRAÎNE :\n      {commande_regeneration()}\n")
        return 1
    print("  ✓ toutes les bibliothèques d'entraînement sont épinglées\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
