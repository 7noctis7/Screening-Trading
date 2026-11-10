#!/usr/bin/env python3
"""make puissance-gate — ce que le gate de promotion peut détecter, vu le registre réel.

Lit le nombre d'essais du registre (`research/hypotheses.jsonl`) et publie, pour la formule
que le gate applique déjà : le Sharpe annualisé minimal selon la durée de l'historique, et
le nombre d'années qu'un Sharpe donné mettrait à être reconnu. Lecture seule : aucun seuil
changé, aucun essai consigné.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.research.protocole_oos import essais_du_ledger  # noqa: E402
from packages.research.puissance_gate import SEUILS, tableau  # noqa: E402


def _cellule(v: float | None, motif: str) -> str:
    return "  jamais" if v is None else format(v, motif)


def main() -> int:
    n = essais_du_ledger()
    t = tableau(n)
    print(f"Registre : {n} essai(s). Hypothèse : {t['hypothese']}.\n")
    print("Sharpe ANNUALISÉ minimal pour passer, selon les années de barres quotidiennes :")
    annees = list(next(iter(t["sharpe_annuel_minimal"].values())))
    print(f"  {'porte':28} " + " ".join(f"{a:>4} ans" for a in annees))
    for nom, ligne in t["sharpe_annuel_minimal"].items():
        print(f"  {nom + f' (DSR > {SEUILS[nom]})':28} "
              + " ".join(_cellule(ligne[a], "8.2f") for a in annees))
    print("\nAnnées de barres quotidiennes pour qu'un Sharpe annualisé VRAI passe :")
    sharpes = list(next(iter(t["annees_necessaires"].values())))
    print(f"  {'porte':28} " + " ".join(f"SR {s:>4}" for s in sharpes))
    for nom, ligne in t["annees_necessaires"].items():
        print(f"  {nom + f' (DSR > {SEUILS[nom]})':28} "
              + " ".join(_cellule(ligne[s], "7.1f") for s in sharpes))
    print("\nLecture : un candidat dont le Sharpe vrai est sous la première table est refusé "
          "PAR CONSTRUCTION,\nqu'il existe ou non. Un « non établi » se lit avec ce seuil.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
