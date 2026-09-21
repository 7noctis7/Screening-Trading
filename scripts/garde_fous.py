#!/usr/bin/env python3
"""Rapport des garde-fous du chemin d'exécution — ce qu'ils ont fait, run après run.

Lit `.cache/garde_fous.json` (écrit par `run_live` à chaque passage) et répond aux
questions que personne ne pouvait poser : combien d'ordres le portail a-t-il réduits,
de combien, pour quelle règle ; combien de fois le disjoncteur AURAIT coupé ; un
garde-fou est-il resté muet parce que tout allait bien, ou parce qu'il ne tournait pas.

NE MESURE RIEN PAR LUI-MÊME : il additionne des comptes-rendus déjà écrits. Sur un
dépôt neuf il affiche UNCALIBRATED, et c'est la bonne réponse — pas des zéros.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.execution.garde_fous import ORDRE, agreger, verdicts  # noqa: E402
from packages.execution.garde_fous_store import charger  # noqa: E402

_LARGEUR = 26


def _fenetre(runs: list[dict], jours: int | None) -> list[dict]:
    if not jours:
        return runs
    limite = (datetime.now(UTC) - timedelta(days=jours)).isoformat()
    return [r for r in runs if str(r.get("horodatage") or "") >= limite]


def _n(v: object, suffixe: str = "") -> str:
    """`n/d` et `0` ne se confondent pas : un effet non mesurable n'est pas un effet nul."""
    if v is None:
        return "n/d"
    if isinstance(v, float):
        return f"{v:,.2f}{suffixe}".replace(",", " ")
    return f"{v}{suffixe}"


def _etats(d: dict) -> str:
    return " ".join(f"{e}×{n}" for e, n in sorted(d.items())) or "—"


def _ligne(nom: str, g: dict | None) -> str:
    if not g:
        return f"  {nom:<{_LARGEUR}} {'JAMAIS OBSERVÉ':<22} {'—':>6} {'—':>6} {'—':>8} {'—':>12}"
    taux = "n/d" if g["taux"] is None else f"{g['taux']*100:.1f} %"
    return (f"  {nom:<{_LARGEUR}} {_etats(g['etats']):<22} "
            f"{g['observations']:>6} {g['declenchements']:>6} {taux:>8} "
            f"{_n(g['effet_usd']):>12}")


def _motifs(nom: str, g: dict | None) -> None:
    if not g or not g.get("motifs"):
        return
    detail = " · ".join(f"{m} ×{n}" for m, n in sorted(g["motifs"].items(),
                                                       key=lambda x: -x[1]))
    print(f"      {nom} — motifs : {detail}")
    if g.get("effet_moyen") is not None:
        print(f"      {nom} — effet moyen par déclenchement : "
              f"{_n(g['effet_moyen'])} $ (à juger, aucun seuil n'est posé ici)")


def _afficher(a: dict, mode: str) -> None:
    n, tot = a["n_runs"], a["n_runs_total"]
    print(f"\n=== GARDE-FOUS DU CHEMIN D'EXÉCUTION — mode « {mode} » ===")
    print(f"{n} run(s) retenu(s) sur {tot} enregistré(s)"
          + (f", du {a['depuis'][:10]} au {a['jusqu_a'][:10]}" if a["depuis"] else ""))
    if not n:
        return
    # « états » se compte en RUNS, « obs. » en décisions. Les deux coïncident pour un
    # garde-fou évalué une fois par run, et divergent pour ceux qui voient chaque ordre :
    # `ACTIVE×1` à côté de `19` observations se lit comme une contradiction si la colonne
    # ne dit pas son unité. (Constaté sur le premier vrai rapport, 21/09.)
    print(f"\n  {'garde-fou':<{_LARGEUR}} {'états (par run)':<22} {'obs.':>6} {'décl.':>6} "
          f"{'taux':>8} {'effet $':>12}")
    for nom in ORDRE:
        g = a["gardes"].get(nom)
        print(_ligne(nom, g))
        _motifs(nom, g)
    inconnus = [k for k in a["gardes"] if k not in ORDRE]
    for nom in sorted(inconnus):
        print(_ligne(nom, a["gardes"][nom]))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", default="live", choices=["live", "dry", "tout"],
                   help="live = passages réels (défaut) · dry = aperçus · tout = les deux")
    p.add_argument("--jours", type=int, default=0,
                   help="ne garder que les N derniers jours (0 = tout l'historique)")
    a = p.parse_args()

    runs = _fenetre(charger(), a.jours)
    if not runs:
        print("\nUNCALIBRATED — aucun compte-rendu de garde-fou enregistré.")
        print("Les compteurs se remplissent au prochain passage de `scripts/run_live.py`.")
        print("Un rapport vide ne dit PAS que les garde-fous n'ont rien fait : il dit "
              "qu'on ne les a pas encore regardés.")
        return
    agrege = agreger(runs, None if a.mode == "tout" else a.mode)
    _afficher(agrege, a.mode)
    lignes = verdicts(agrege)
    if lignes:
        print("\nCE QU'IL FAUT REGARDER")
        for x in lignes:
            print(f"  · {x}")
    print("\nLecture : « JAMAIS OBSERVÉ » = désarmé ou jamais atteint · « ACTIVE » + 0 "
          "déclenchement = il tourne sans jamais mordre ·\n"
          "« UNCALIBRATED » = il a tourné sans pouvoir conclure · « ERROR » = il est "
          "tombé en panne, et le run a continué sans lui.")


if __name__ == "__main__":
    main()
