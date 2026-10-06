"""Cadence de rebalancement : la production décide au rythme de la règle MESURÉE.

POURQUOI (audit E[Gain], 06/10). Le seul chiffre publié de la règle tradée vient du
rejeu, qui décide tous les `CADENCE_DEFAUT` séances (`preset_rejeu.PAS_DEFAUT`). La
production, elle, rebalançait CHAQUE jour : un rythme jamais mesuré, et une rotation
de poussière (audit de turnover du 24/09 : détention médiane d'un jour, 41 fermetures
par semaine).
Les deux programmes ne faisaient pas la même chose. Ils partagent désormais cette
constante : le rejeu la lit comme pas par défaut, `run_live` comme cadence.

RÈGLE. Un passage n'agit que si au moins `cadence()` séances se sont écoulées depuis le
dernier rebalancement CONSTATÉ CHEZ LE COURTIER (même source que la garde journalière :
le compte, pas un fichier). Exceptions, toujours :
  - réduction de risque (kill-switch, drawdown, disjoncteur) : un désengagement n'attend
    jamais (AGENTS.md, principe 2) ;
  - historique illisible : le doute profite au passage (comme la garde journalière) ;
  - `--forcer` (géré par l'appelant).

`QUANT_CADENCE_JOURS=1` rétablit l'ancien rythme quotidien. Séances = jours ouvrés
(lundi-vendredi) : les jours fériés comptent comme des séances, ce qui avance au plus
d'un jour le passage suivant.
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import date

import numpy as np

CADENCE_DEFAUT = 5
ENV = "QUANT_CADENCE_JOURS"


def cadence() -> int:
    """Séances minimales entre deux rebalancements (≥ 1). Illisible → défaut."""
    try:
        return max(1, int(os.environ.get(ENV, CADENCE_DEFAUT)))
    except (TypeError, ValueError):
        return CADENCE_DEFAUT


def dernier_passage(ordres: list[dict]) -> date | None:
    """Dernier jour où le compte a réellement été rebalancé (mêmes seuils que la garde
    journalière : plusieurs ordres, notionnel non négligeable)."""
    from packages.execution.garde_journaliere import (
        NOTIONNEL_MINIMUM,
        ORDRES_MINIMUM,
        jour_utc,
    )
    par_jour: dict[date, list[float]] = defaultdict(list)
    for o in ordres or []:
        j = jour_utc(str(o.get("date") or ""))
        if j is not None and float(o.get("qty") or 0) > 0:
            par_jour[j].append(abs(float(o.get("notional") or 0)))
    jours = [j for j, n in par_jour.items()
             if len(n) >= ORDRES_MINIMUM and sum(n) >= NOTIONNEL_MINIMUM]
    return max(jours) if jours else None


def seances_ecoulees(depuis: date, jusqu_a: date) -> int:
    """Séances (jours ouvrés) de `depuis` exclu à `jusqu_a` inclus."""
    return int(np.busday_count(depuis, jusqu_a)) if jusqu_a > depuis else 0


def evaluer(ordres: list[dict], aujourd_hui: date, *, reduction: float = 1.0,
            pas: int | None = None) -> dict:
    """{passer, motif, dernier, seances, cadence} — décision de ce passage."""
    c = cadence() if pas is None else max(1, pas)
    base = {"cadence": c, "dernier": None, "seances": None}
    if reduction < 1.0:
        return {**base, "passer": True, "motif": "réduction de risque"}
    dernier = dernier_passage(ordres)
    if dernier is None:
        return {**base, "passer": True, "motif": "aucun rebalancement constaté"}
    n = seances_ecoulees(dernier, aujourd_hui)
    passer = n >= c
    return {"cadence": c, "dernier": dernier.isoformat(), "seances": n,
            "passer": passer,
            "motif": "échéance atteinte" if passer else "avant l'échéance"}
