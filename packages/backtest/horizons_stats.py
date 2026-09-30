"""Horizons de détention et synthèse par dimension de la grille `scenarios_horizons`.

Un horizon de H années se mesure sur des fenêtres GLISSANTES de H années COMPLÈTES, une
qui démarre chaque mois : la médiane dit ce qu'un investisseur entré à une date quelconque
aurait obtenu, la part de fenêtres battant le buy & hold dit si la règle aide vraiment.
Sans une seule fenêtre complète, l'horizon n'a pas de chiffre (n = 0) : UNCALIBRATED.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections.abc import Callable
from datetime import datetime, timedelta
from statistics import median

import numpy as np

DIMENSIONS = ("strategie", "sortie", "frequence")


def _dd(serie: np.ndarray) -> float:
    pic = np.maximum.accumulate(serie)
    return float((serie / pic - 1.0).min())


def fenetres(eq, bh, jours: list[str], annees: float, pas: int) -> dict:
    """Rendement annualisé, drawdown et comparaison au B&H sur chaque fenêtre de H ans."""
    dts = [datetime.fromisoformat(j) for j in jours]
    e, b = np.asarray(eq, float), np.asarray(bh, float)
    rs, rbs, dds = [], [], []
    for s in range(0, len(dts), max(1, pas)):
        fin = bisect_left(dts, dts[s] + timedelta(days=365.25 * annees))
        if fin >= len(dts):
            break
        ans = (dts[fin] - dts[s]).total_seconds() / (365.25 * 86400)
        rs.append((e[fin] / e[s]) ** (1 / ans) - 1)
        rbs.append((b[fin] / b[s]) ** (1 / ans) - 1)
        dds.append(_dd(e[s:fin + 1]))
    if not rs:
        return {"n": 0, "rend_annuel_median": math.nan, "rend_bh_median": math.nan,
                "part_positive": math.nan, "part_bat_bh": math.nan, "maxdd_median": math.nan}
    r, rb = np.array(rs), np.array(rbs)
    return {"n": len(rs), "rend_annuel_median": float(np.median(r)),
            "rend_bh_median": float(np.median(rb)), "part_positive": float((r > 0).mean()),
            "part_bat_bh": float((r > rb + 1e-12).mean()), "maxdd_median": float(median(dds))}


def _valeur(ligne: dict, metrique: str | Callable) -> float:
    v = metrique(ligne) if callable(metrique) else ligne.get(metrique)
    return v if isinstance(v, (int, float)) and math.isfinite(v) else math.nan


def par_dimension(lignes: list[dict], metrique: str | Callable) -> dict:
    """Médiane de la métrique pour chaque valeur de chaque dimension de la grille."""
    out: dict = {}
    for dim in DIMENSIONS:
        groupes: dict = {}
        for li in lignes:
            groupes.setdefault(li[dim], []).append(_valeur(li, metrique))
        out[dim] = {k: (float(median([x for x in v if math.isfinite(x)]))
                        if any(math.isfinite(x) for x in v) else math.nan)
                    for k, v in groupes.items()}
    return out


def meilleurs(lignes: list[dict], metrique: str | Callable, top: int = 5) -> list[dict]:
    """Configurations classées par la MÉDIANE entre actifs de la métrique (pas le meilleur
    actif : un seul titre hors norme ne doit pas faire gagner une règle)."""
    groupes: dict = {}
    for li in lignes:
        groupes.setdefault(li["id"], []).append(_valeur(li, metrique))
    classes = [(float(median([x for x in v if math.isfinite(x)])), k, len(v))
               for k, v in groupes.items() if any(math.isfinite(x) for x in v)]
    classes.sort(reverse=True)
    return [{"id": k, "valeur": v, "n_actifs": n} for v, k, n in classes[:top]]
