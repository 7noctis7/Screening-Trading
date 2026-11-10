"""Ce qu'ENCAISSE un classement : top-k long-only, net de coûts, et ses épisodes de détention.

POURQUOI (10/11). Un IC dit que le classement ordonne les rendements ; il ne dit pas ce
qu'un portefeuille en retire une fois payé le prix d'exécution et la rotation. Ce module
rejoue la règle la plus simple qui soit fidèle à la production, sans ses portes :
- décision au close du jour t, tous les `pas` jours (cadence de production) ;
- achat au close du jour t + 1 (jamais au close qui a servi au signal) ;
- top-k équipondéré, conservé sans retouche jusqu'à l'exécution suivante ;
- coût par côté facturé sur la ROTATION réelle (poids dérivés compris), le jour d'exécution.
La référence est l'univers équipondéré de la MÊME coupe, rebalancé aux mêmes dates et sans
coût : un avantage laissé à la référence.

CE QUE ÇA NE CONTIENT PAS. Les portes de production (régime, ampleur, plafond de drawdown),
l'ERC et le cœur indiciel : c'est la sélection seule qui est mesurée.

RIEN N'EST INVENTÉ. Un titre choisi sans clôture le jour d'exécution n'est pas acheté : son
poids reste en espèces, et l'ordre est compté « non exécutable ». Une barre manquante d'un
titre détenu vaut 0 ce jour-là et est comptée.

STATUT : CANDIDATE. Module de recherche, aucun appelant en production, aucun ordre.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from packages.research.ic_classement import N_TITRES_MIN
from packages.research.labo_classement import Classement

STATUT = "CANDIDATE"


def decisions(pan: dict[str, Any], classement: Classement, pas: int, debut: int,
              top_k: int) -> tuple[list[dict[str, Any]], int]:
    """[{t, e, cols, coupe}] : `cols` = top-k au jour t, `e` = index d'exécution (t + 1)."""
    out: list[dict[str, Any]] = []
    sautees = 0
    for t in range(debut, len(pan["jours"]) - 2, max(1, pas)):
        sc = classement(pan, t)
        if sc is None or int(np.isfinite(sc).sum()) < max(top_k, N_TITRES_MIN):
            sautees += 1
            continue
        coupe = np.flatnonzero(np.isfinite(sc))
        ordre = coupe[np.argsort(-sc[coupe], kind="stable")]
        out.append({"t": t, "e": t + 1, "cols": ordre[:top_k], "coupe": coupe})
    return out, sautees


def _periode(R: np.ndarray, poids: dict[int, float], e: int,
             fin: int) -> tuple[np.ndarray, dict[int, float], int]:
    """Rendements quotidiens de e + 1 à `fin`, poids en fin de période, barres manquantes."""
    cols = list(poids)
    seg = R[e + 1:fin + 1][:, cols]
    manquantes = int(np.isnan(seg).sum())
    valeurs = np.cumprod(1.0 + np.nan_to_num(seg, nan=0.0), axis=0) * np.array(
        [poids[c] for c in cols])
    total = (1.0 - sum(poids.values())) + valeurs.sum(axis=1)
    if total.size == 0:
        return total, dict(poids), manquantes
    r = total / np.concatenate(([1.0], total[:-1])) - 1.0
    return r, {c: float(valeurs[-1, i] / total[-1]) for i, c in enumerate(cols)}, manquantes


def _couts(cout_par_cote: float | np.ndarray, n_titres: int) -> np.ndarray:
    """Coût par côté de chaque titre (fraction) : un scalaire vaut pour tous."""
    return np.broadcast_to(np.asarray(cout_par_cote, float), (n_titres,))


def simuler(pan: dict[str, Any], decs: list[dict[str, Any]], cle: str,
            cout_par_cote: float | np.ndarray) -> dict[str, Any]:
    """Rendements quotidiens nets du portefeuille équipondéré sur `decs[i][cle]`.

    `cout_par_cote` : fraction par côté, scalaire ou une valeur PAR TITRE (une crypto ne
    coûte pas ce que coûte une action)."""
    R, C = pan["R"], pan["C"]
    n = len(pan["jours"])
    cout = _couts(cout_par_cote, C.shape[1])
    r = np.zeros(n)
    rotation_jour = np.zeros(n)
    rotations: list[float] = []
    precedents: dict[int, float] = {}
    manquantes = non_executables = 0
    for k, d in enumerate(decs):
        e = d["e"]
        fin = decs[k + 1]["e"] if k + 1 < len(decs) else n - 1
        cols = [int(c) for c in d[cle]]
        cible = {c: 1.0 / len(cols) for c in cols if np.isfinite(C[e, c])}
        non_executables += len(cols) - len(cible)
        ecarts = {c: abs(cible.get(c, 0.0) - precedents.get(c, 0.0))
                  for c in set(cible) | set(precedents)}
        rotations.append(sum(ecarts.values()))
        rotation_jour[e] = rotations[-1]
        r[e] -= sum(d_w * cout[c] for c, d_w in ecarts.items())
        jour, precedents, m = _periode(R, cible, e, fin)
        r[e + 1:fin + 1] += jour
        manquantes += m
    depart = decs[0]["e"] if decs else n
    return {"r": r[depart:], "jours": pan["jours"][depart:], "rotations": rotations,
            "rotation_par_jour": rotation_jour[depart:],
            "barres_manquantes": manquantes, "ordres_non_executables": non_executables}


def episodes(pan: dict[str, Any], decs: list[dict[str, Any]],
             cout_par_cote: float | np.ndarray) -> tuple[list[float], dict[str, Any]]:
    """Rendement NET de chaque détention continue d'un titre dans le top-k.

    Entrée au prix d'exécution de la première sélection, sortie au prix d'exécution de la
    première décision qui ne le retient plus, deux côtés de coût."""
    C = pan["C"]
    cout = _couts(cout_par_cote, C.shape[1])
    nets: list[float] = []
    entree: dict[int, int] = {}
    non_valorisables = 0
    for d in decs:
        actuels = {int(c) for c in d["cols"]}
        for c in [c for c in entree if c not in actuels]:
            p0, p1 = C[entree.pop(c), c], C[d["e"], c]
            if np.isfinite(p0) and np.isfinite(p1):
                nets.append(float(p1 / p0 - 1.0 - 2.0 * cout[c]))
            else:
                non_valorisables += 1
        for c in actuels:
            entree.setdefault(c, d["e"])
    return nets, {"episodes_clos": len(nets), "episodes_ouverts": len(entree),
                  "episodes_non_valorisables": non_valorisables}


def statistiques_episodes(nets: list[float]) -> dict[str, Any]:
    """Espérance, taux de gain, gain et perte moyens, profit factor — IC 95 % par bootstrap."""
    from packages.research.aller_retour import esperance
    res = esperance(nets, [1.0] * len(nets))
    if not res.get("available"):
        return res
    x = np.asarray(nets)
    pertes = float(-x[x <= 0].sum())
    res["profit_factor"] = float(x[x > 0].sum() / pertes) if pertes > 0 else None
    return res
