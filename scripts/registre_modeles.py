#!/usr/bin/env python3
"""Le registre de modèles, en clair — et le rollback quand il faut.

  python scripts/registre_modeles.py                      # état + historique
  python scripts/registre_modeles.py --rollback           # revenir à la production d'avant
  python scripts/registre_modeles.py --rejeter VERSION --motif "PBO 0,88"
  python scripts/registre_modeles.py --promouvoir VERSION --motif "validé en paper"

La promotion depuis cette ligne de commande est un acte HUMAIN et délibéré. `train_model`
enregistre et applique la décision automatique de `promotion.should_promote` ; ici, c'est
quelqu'un qui tranche — et le motif est obligatoire, parce qu'un registre sans motifs ne
répond pas à « pourquoi ce modèle est-il en production ? ».
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _ligne(e) -> str:
    m = e.manifest or {}
    metriques = m.get("metriques") or {}
    auc = metriques.get("auc")
    marque = {"production": "▶", "candidate": "·", "archived": "□", "rejected": "✗"}
    return (f" {marque.get(e.statut, '?')} {e.statut:11s} {e.version:44s} "
            f"AUC {auc if auc is not None else 'n/d':>6} "
            f"· seed {m.get('seed')} · {m.get('materiel') or '?'}")


def afficher(reg) -> None:
    prod = reg.production()
    print(f"\n  PRODUCTION : {prod.version if prod else '(aucune)'}")
    if not reg.entrees:
        print("  (registre vide — aucun entraînement n'a encore été tracé)")
        return
    print("  " + "─" * 100)
    for statut in ("production", "candidate", "archived", "rejected"):
        for e in reg.par_statut(statut):
            print(_ligne(e))
            repro = (e.manifest or {}).get("git_commit", "")
            if repro.endswith("-sale"):
                print("      ⚠ entraîné depuis un arbre GIT MODIFIÉ — non reproductible")
    print("  " + "─" * 100)
    soucis = reg.incoherences()
    for s in soucis:
        print(f"  ⚠ {s}")
    if not soucis:
        print("  ✓ aucune incohérence")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rollback", action="store_true", help="revenir à la production précédente")
    ap.add_argument("--promouvoir", metavar="VERSION")
    ap.add_argument("--rejeter", metavar="VERSION")
    ap.add_argument("--motif", default="", help="obligatoire pour toute action")
    a = ap.parse_args()

    from packages.mlops.registre import Registre
    reg = Registre()

    action = a.rollback or a.promouvoir or a.rejeter
    if action and not a.motif:
        print("⛔ --motif est obligatoire : un registre sans motifs ne dit pas pourquoi.",
              file=sys.stderr)
        return 2

    if a.rollback:
        ok, dit = reg.rollback(a.motif)
    elif a.promouvoir:
        ok, dit = reg.promouvoir(a.promouvoir, a.motif)
    elif a.rejeter:
        ok, dit = reg.rejeter(a.rejeter, a.motif)
    else:
        afficher(reg)
        return 0

    print(("✅ " if ok else "⛔ ") + dit)
    afficher(reg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
