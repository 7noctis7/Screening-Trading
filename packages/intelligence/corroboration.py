"""Corroboration croisée — compter des sources INDÉPENDANTES, pas des échos.

Le piège que ce module existe pour éviter : trois comptes qui relaient le même post d'origine
ne sont pas trois confirmations, c'est une seule information vue trois fois. Sur X, la reprise
est le mode de diffusion normal — compter naïvement produirait une confirmation instantanée
pour n'importe quelle rumeur virale.

Deux sources sont INDÉPENDANTES si elles ne partagent ni le même compte, ni la même origine
déclarée. On ne peut pas prouver l'indépendance en général ; on peut refuser les cas évidents
de dépendance, et c'est déjà l'essentiel du travail.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.intelligence.sources import Niveau, Source


@dataclass(frozen=True)
class Rapport:
    """Une reprise d'une information par une source donnée."""
    source: Source
    origine: str = ""      # d'où la source dit tenir l'information ("" = origine non déclarée)
    url: str = ""


@dataclass(frozen=True)
class Bilan:
    independantes: int
    primaire: bool
    ecartees: list[str]
    detail: list[str]


def croiser(rapports: list[Rapport]) -> Bilan:
    """Compte les confirmations réellement indépendantes.

    Sont écartés : les doublons de compte, et les reprises d'une origine déjà comptée. Une
    source de niveau D ou E ne compte JAMAIS comme confirmation — elle sert à détecter, pas à
    confirmer ; l'admettre reviendrait à laisser un réseau de comptes anonymes s'auto-valider.
    """
    vus_comptes: set[str] = set()
    vues_origines: set[str] = set()
    ecartees: list[str] = []
    detail: list[str] = []
    n = 0
    primaire = False
    for r in rapports:
        h = r.source.handle.lower()
        if h in vus_comptes:
            ecartees.append(f"{r.source.handle} : compte déjà compté")
            continue
        vus_comptes.add(h)
        if r.source.niveau in (Niveau.D_SECONDAIRE, Niveau.E_FAIBLE):
            ecartees.append(f"{r.source.handle} : niveau {r.source.niveau.value} — "
                            "détection seulement, jamais confirmation")
            continue
        o = (r.origine or "").strip().lower()
        if o and o in vues_origines:
            ecartees.append(f"{r.source.handle} : reprise de « {r.origine} », déjà compté")
            continue
        if o:
            vues_origines.add(o)
        n += 1
        detail.append(f"{r.source.handle} (niveau {r.source.niveau.value})"
                      + (f", origine « {r.origine} »" if r.origine else ", origine propre"))
        if r.source.niveau is Niveau.A_PRIMAIRE and r.source.verifie:
            primaire = True
    return Bilan(n, primaire, ecartees, detail)
