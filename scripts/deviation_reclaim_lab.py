#!/usr/bin/env python3
"""Le motif déviation → reclaim → consolidation prédit-il quelque chose ? — MESURÉ.

LA QUESTION, ET POURQUOI ELLE PASSE AVANT TOUTE STRATÉGIE. Une spec décrivant un motif
de price action est une HYPOTHÈSE, pas un résultat. Ce banc la met à l'épreuve sur
l'historique réel avant qu'une ligne de stratégie ne soit écrite — dix minutes ici
évitent des semaines de câblage inutile, comme pour `signal_lab`.

CE QU'IL COMPARE, ET C'EST LE POINT. La primitive `liquidite_ict.sfp` existe depuis le
02/09 : la mèche prend la liquidité, la clôture la rend, en UNE barre. La machine à
états ajoute la séparation déviation/reclaim sur plusieurs barres, puis l'acceptation.
Si l'ajout n'améliore pas la prédiction, il ne sert à rien — et c'est une réponse, pas
un échec. Les scoreurs sont donc notés sur EXACTEMENT les mêmes événements, ce qui rend
la comparaison APPARIÉE : même barre, plusieurs avis, une différence testable.

LE PIÈGE QU'IL FERME. Un motif qui se déclenche rarement finit toujours par « marcher »
sur un échantillon choisi. Mesuré ici sur une marche aléatoire de 400 barres, la machine
atteint CONSOLIDATION_CONFIRMED dix fois : le motif existe dans le bruit pur. D'où le
gate emprunté à `alpha_incremental` — placebo par permutation, Sharpe déflaté, et
correction de tests multiples sur TOUS les scoreurs essayés.

CE QUE CE BANC NE FAIT PAS. Il ne note pas le setup (aucun score 0-100 : les poids
seraient choisis, pas mesurés), il ne calcule pas de reward/risk comme filtre (cible et
résistance sortent de la même analyse que le ratio, qui mesurerait alors sa propre
générosité), et il ne conclut rien sur un timeframe 4H — la base de ce dépôt est
QUOTIDIENNE, et tout chiffre intraday serait inventé.

    python scripts/deviation_reclaim_lab.py                 # 120 titres, hold 5 j
    python scripts/deviation_reclaim_lab.py --titres 200 --hold 10 --pas 1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.indicators.deviation_reclaim import (  # noqa: E402
    CONSOLIDATION_CONFIRMED,
    DEVIATION_DETECTED,
    EXPANSION_CONFIRMED,
    PIVOT,
    RECLAIM_CONFIRMED,
    etat,
    pivots_causaux,
)
from packages.research.alpha_incremental import Evenement, comparer  # noqa: E402

# Rang des états : « au moins RECLAIM » se lit sur un ordre, pas sur une égalité.
RANG = {DEVIATION_DETECTED: 1, RECLAIM_CONFIRMED: 2,
        CONSOLIDATION_CONFIRMED: 3, EXPANSION_CONFIRMED: 4}
SEUIL_P = 0.05
SEUIL_DSR = 0.5


def _rendement(barres, i: int, hold: int, lag: int) -> float | None:
    """Rendement FORWARD, entrée au close suivant le signal.

    `lag=1` n'est pas une précaution cosmétique : entrer au close de la barre qui porte
    le signal suppose d'avoir vu, décidé et exécuté avant cette clôture. C'est le
    look-ahead que tout le monde dénonce et que beaucoup d'études commettent.
    """
    e, s = i + lag, i + lag + hold
    if s >= len(barres) or float(barres[e].close) <= 0:
        return None
    return float(barres[s].close) / float(barres[e].close) - 1.0


def _sfp_long(barres, i: int) -> bool:
    from packages.indicators.liquidite_ict import sfp
    return bool(sfp(barres, i).get("sens") == "long")


def _scores(e: dict, barres, i: int) -> dict[str, float]:
    """Les avis des scoreurs à cette barre. Binaires : 1 = allumé, 0 = muet."""
    rang = RANG.get(e["etat"], 0)
    conso = e.get("consolidation") or {}
    return {
        "sfp_seul (primitive du 02/09)": float(_sfp_long(barres, i)),
        "deviation": float(rang >= 1),
        "reclaim": float(rang >= 2),
        "consolidation": float(rang >= 3),
        "consolidation + contraction":
            float(rang >= 3 and bool(conso.get("contraction"))),
    }


def _collecter(data: dict, syms: list[str], hold: int, pas: int, lag: int,
               depart: int) -> tuple[list[Evenement], dict[str, list[float]]]:
    """Un passage unique : les événements ET tous les avis, sur le même échantillon."""
    evenements: list[Evenement] = []
    scores: dict[str, list[float]] = {}
    for sym in syms:
        barres = data[sym]
        if len(barres) < depart + hold + lag + 10:
            continue
        piv = pivots_causaux(barres, PIVOT)
        for i in range(depart, len(barres) - hold - lag, pas):
            r = _rendement(barres, i, hold, lag)
            if r is None:
                continue
            e = etat(barres, i, pivots=piv)
            evenements.append(Evenement(symbole=sym, jour=str(barres[i].ts)[:10],
                                        titre=e["etat"], rendement=r))
            for nom, v in _scores(e, barres, i).items():
                scores.setdefault(nom, []).append(v)
    return evenements, scores


def _afficher(res: dict, hold: int) -> list[str]:
    print(f"\n  {res['n_evenements']} barres notées · horizon {hold} j · "
          f"{res['n_essais']} scoreurs (correction de tests multiples appliquée)\n")
    print(f"  {'scoreur':<32} {'allumé':>8} {'IC':>8} {'Sharpe':>8} {'DSR':>7} "
          f"{'placebo':>9}  verdict")
    print("  " + "-" * 92)
    retenus = []
    for nom, m in res["mesures"].items():
        p = m.get("p_placebo")
        ok = (p is not None and p < SEUIL_P and (m.get("dsr") or 0) > SEUIL_DSR)
        if ok:
            retenus.append(nom)
        print(f"  {nom:<32} {m['part_notee']:>7.1%} {m['ic']:>+8.4f} "
              f"{m['sharpe']:>+8.3f} {m['dsr']:>7.3f} {p:>9.6f}  "
              f"{'RETENU' if ok else 'rejeté'}")
    return retenus


def _ecarts(res: dict) -> None:
    ecarts = res.get("ecarts") or []
    if not ecarts:
        return
    print("\n  ÉCARTS APPARIÉS — le motif complet apporte-t-il quelque chose ?\n")
    for e in ecarts:
        print(f"    {str(e.get('paire', e))[:88]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--titres", type=int, default=120)
    ap.add_argument("--hold", type=int, default=5)
    ap.add_argument("--pas", type=int, default=1)
    ap.add_argument("--lag", type=int, default=1)
    ap.add_argument("--depart", type=int, default=60)
    ap.add_argument("--tirages", type=int, default=500)
    a = ap.parse_args()

    print(__doc__.split("    python")[0].rstrip())
    from scripts.sizing_lab import _donnees
    data, _ac, mode, n_reels, _d, _f = _donnees()
    if n_reels < 30:
        print("\n  ⚠ UNCALIBRATED — aucune base de prix réelle branchée. Ce banc ne")
        print("    décide de rien : lancer sur la machine qui porte les bases.")
        return 2
    syms = sorted(data)[:a.titres]
    print(f"\n  {len(syms)} titres · mode {mode} · pas {a.pas} · entrée à J+{a.lag}")

    evenements, scores = _collecter(data, syms, a.hold, a.pas, a.lag, a.depart)
    if len(evenements) < 30:
        print(f"\n  ⚠ UNCALIBRATED — {len(evenements)} événements, "
              "trop peu pour conclure.")
        return 2

    res = comparer(evenements, scores, hold=a.hold, tirages=a.tirages)
    retenus = _afficher(res, a.hold)
    _ecarts(res)

    print(f"\n  VERDICT : {len(retenus)} scoreur(s) passent placebo < {SEUIL_P} ET "
          f"DSR > {SEUIL_DSR}")
    if not retenus:
        print("    → RIEN à câbler. Le motif ne se distingue pas du hasard sur cet")
        print("      échantillon, et c'est une réponse — pas un échec du banc.")
    else:
        print("    → " + " · ".join(retenus))
        print("    Prochaine étape : PAS une stratégie. D'abord `signal_lab` pour le")
        print("    recouvrement avec le filtre de production — un signal qui répète")
        print("    l'existant n'ajoute rien, quel que soit son IC.")
    print("\n  Rappel : aucun timeframe 4H ici. La base est QUOTIDIENNE ; la jambe")
    print("  d'exécution de la spec reste UNCALIBRATED tant qu'aucune donnée intraday")
    print("  n'existe (vault/03_TODO.md, P2).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
