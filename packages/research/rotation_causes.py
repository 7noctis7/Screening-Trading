"""D'où vient la rotation ? Décomposition du turnover des CIBLES de production.

POURQUOI (audit de l'espérance, 06/10, constat F10 et rang 4). La rotation live paraît
plus de cinq fois supérieure à celle du rejeu, et la détention médiane est d'un jour.
Avant de régler une bande ou une hystérésis, il faut savoir QUI demande les ordres.

DÉCOMPOSITION ADDITIVE entre deux décisions consécutives (poids w0 → w1, satellite seul,
sans le cœur indiciel) :

    total          = Σ |w1 − w0|                      (tous les noms)
    sélection      = Σ |w| des noms entrés ou sortis  (le top-12 a changé)
    échelle        = |Σ w1 − Σ w0| sur les noms restés (l'exposition brute a bougé :
                     DD-target, porte de régime, ampleur)
    redistribution = le reste sur les noms restés     (ERC, tilt, plafond, blackout)

`total = sélection + échelle + redistribution` exactement (l'échelle est le minimum de
turnover qu'impose la variation de la somme ; la redistribution est ≥ 0).

ALLERS-RETOURS. Un nom qui sort puis revient en moins de `fenetre` décisions est
le symptôme d'une règle qui bascule sans hystérésis (constat F3).

Ce sont les cibles, AVANT bande et plancher : ce module dit d'où vient l'INTENTION de
trader ; le rejeu dit ce qui est exécuté. Diagnostic, pas un essai au registre.
"""

from __future__ import annotations

FENETRE_ALLER_RETOUR = 3


def decomposer(w0: dict, w1: dict) -> dict:
    """Turnover entre deux jeux de poids, en quatre termes additifs (fractions)."""
    entres = set(w1) - set(w0)
    sortis = set(w0) - set(w1)
    restes = set(w0) & set(w1)
    selection = sum(abs(w1[s]) for s in entres) + sum(abs(w0[s]) for s in sortis)
    delta_restes = sum(abs(w1[s] - w0[s]) for s in restes)
    echelle = abs(sum(w1[s] for s in restes) - sum(w0[s] for s in restes))
    return {"total": selection + delta_restes, "selection": selection,
            "echelle": echelle, "redistribution": delta_restes - echelle,
            "entres": sorted(entres), "sortis": sorted(sortis)}


def _allers_retours(sequence: list[dict], fenetre: int) -> int:
    """Nombre de retours d'un nom sorti depuis moins de `fenetre` décisions."""
    derniere_sortie: dict[str, int] = {}
    n = 0
    for k in range(1, len(sequence)):
        avant, apres = set(sequence[k - 1]), set(sequence[k])
        for s in avant - apres:
            derniere_sortie[s] = k
        for s in apres - avant:
            if s in derniere_sortie and k - derniere_sortie[s] <= fenetre:
                n += 1
    return n


def agreger(decisions: list, fenetre: int = FENETRE_ALLER_RETOUR) -> dict:
    """Somme des termes sur une suite [(jour, poids)] ; parts du total et comptes."""
    poids = [w or {} for _, w in decisions]
    termes = {"total": 0.0, "selection": 0.0, "echelle": 0.0, "redistribution": 0.0}
    n_entrees = n_sorties = n_vides = 0
    for k in range(1, len(poids)):
        d = decomposer(poids[k - 1], poids[k])
        for cle in termes:
            termes[cle] += d[cle]
        n_entrees += len(d["entres"])
        n_sorties += len(d["sortis"])
        n_vides += int(not poids[k])
    tot = termes["total"]
    parts = {f"part_{c}": (termes[c] / tot if tot > 0 else None)
             for c in ("selection", "echelle", "redistribution")}
    return {"n_decisions": len(poids), **termes, **parts,
            "turnover_moyen_par_decision": tot / max(1, len(poids) - 1),
            "n_entrees": n_entrees, "n_sorties": n_sorties,
            "allers_retours": _allers_retours(poids, fenetre),
            "fenetre_aller_retour": fenetre, "decisions_vides": n_vides}
