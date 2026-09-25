"""UNE seule politique de fusion des bases de prix, et la trace de qui a produit quoi.

LE DÉFAUT QUE CE MODULE SUPPRIME. Le dépôt fusionnait les mêmes bases selon DEUX règles
opposées, à deux endroits :

    `_load_prices`   `merged.setdefault(jour, barre)`   → le PREMIER provider gagne
    `merge_bars`     `target[jour] = (ts, close)`       → le DERNIER provider gagne

Mêmes bases, mêmes dates, deux vérités. Mesuré sur le cœur QQQ : **0,71 %/an d'écart**
entre les deux lectures. Ce n'est pas une divergence d'opinion sur un détail — c'est le
même actif qui a deux historiques selon la fonction qui le demande.

QUELLE RÈGLE EST LA BONNE, ET POURQUOI. La base longue (`YAHOO.db`) porte un historique
AJUSTÉ ; `market.db` est une couche de mise à jour quotidienne (yfinance, barres
brutes).
Laisser la seconde écraser la première insère une discontinuité raw/ajusté AU MILIEU de
l'historique : les rendements de part et d'autre de la couture ne sont plus comparables,
et rien ne le signale. La base longue garde donc la priorité, et la couche fraîche
COMPLÈTE les dates absentes — ce qui suffit à la fraîcheur, puisque les dates récentes
sont précisément celles qui manquent à l'historique.

C'est la règle qu'appliquait déjà `_load_prices`, avec sa raison écrite en commentaire.
`merge_bars` faisait l'inverse sans jamais dire pourquoi. On garde la règle motivée.

CE QUE LE LIGNAGE APPORTE. Sans lui, « d'où vient cette barre ? » se re-déduit à chaque
fois en relisant le code de fusion — et se re-déduit FAUX, comme ici des mois durant. Le
lignage l'enregistre : chaque jour retenu porte le nom de la source qui l'a fourni. La
question devient une lecture, plus une enquête.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from packages.core.models import Bar

# Écart relatif au-delà duquel deux sources sont dites en DÉSACCORD sur une date. Un
# arrondi de sérialisation vaut ~1e-9 ; 1e-6 laisse passer le bruit sans laisser passer
# une différence d'ajustement (qui se compte en pourcents).
TOLERANCE_DESACCORD = 1e-6


def jour(valeur: object) -> str:
    """Clé de fusion : le JOUR, quelle que soit la forme reçue (datetime, date, str)."""
    if isinstance(valeur, datetime):
        return valeur.date().isoformat()
    if isinstance(valeur, date):
        return valeur.isoformat()
    return str(valeur)[:10]


def fusionner(cible: dict, barres: Iterable[Bar], *, source: str | None = None,
              lignage: dict[str, str] | None = None) -> int:
    """Ajoute `barres` à `cible` SANS écraser. Renvoie le nombre de jours ajoutés.

    « Sans écraser » est toute la règle : la première source qui fournit une date la
    garde, les suivantes ne comblent que les trous. Inverser produit la discontinuité
    raw/ajusté décrite en tête de module.

    `lignage`, s'il est fourni, reçoit `jour → source` pour les jours RETENUS — donc
    jamais réécrit non plus : la trace suit la donnée, pas la dernière tentative."""
    ajoutes = 0
    for barre in barres:
        cle = jour(barre.ts)
        if cle in cible:
            continue
        cible[cle] = (barre.ts, float(barre.close))
        if lignage is not None and source is not None:
            lignage[cle] = source
        ajoutes += 1
    return ajoutes


def provenance(lignage: dict[str, str]) -> dict[str, int]:
    """Nombre de jours retenus PAR SOURCE. Le tableau de bord d'une fusion."""
    out: dict[str, int] = {}
    for src in lignage.values():
        out[src] = out.get(src, 0) + 1
    return out


def desaccords(par_source: dict[str, dict[str, float]],
               tolerance: float = TOLERANCE_DESACCORD) -> list[dict]:
    """Jours où DEUX sources donnent un cours différent pour le même actif.

    C'est la mesure qui manquait. Tant qu'on ne l'a pas, « les bases sont d'accord » est
    une hypothèse ; après, c'est un nombre. Un désaccord ne dit pas quelle source a
    raison — il dit que le choix de priorité CHANGE le résultat, donc qu'il doit être
    motivé plutôt que subi."""
    jours: dict[str, dict[str, float]] = {}
    for src, serie in par_source.items():
        for j, close in serie.items():
            jours.setdefault(j, {})[src] = float(close)
    out = []
    for j, valeurs in sorted(jours.items()):
        if len(valeurs) < 2:
            continue
        lo, hi = min(valeurs.values()), max(valeurs.values())
        if abs(hi - lo) > tolerance * max(1.0, abs(hi)):
            out.append({"jour": j, "valeurs": valeurs,
                        "ecart_relatif": (hi - lo) / abs(hi) if hi else 0.0})
    return out


# Un facteur d'ajustement est CONSTANT sur le recouvrement : au-delà de cette dispersion
# relative du rapport des cours, le désaccord n'est pas un ajustement et l'on ne touche à rien.
DISPERSION_MAX_FACTEUR = 1e-3
ECART_MIN_FACTEUR = 5e-3          # sous 0,5 %, les deux bases sont dans le même référentiel


def rebaser_base_longue(longue: list[Bar], maj: list[Bar]) -> tuple[list[Bar], float | None]:
    """Remet la base longue dans le référentiel d'ajustement de la maj (QML-016).

    `YAHOO.db` est ajustée à la date de son export ; `market.db` est ré-ajustée à chaque
    split/dividende. Après une opération postérieure à l'export, les deux bases diffèrent
    d'un facteur CONSTANT sur leurs dates communes — et la jonction fabrique un faux
    rendement (−90 % pour un split 10:1). Si le rapport maj/longue est constant et
    s'écarte de 1, toute la base longue est multipliée par ce facteur : aucun rendement
    interne ne change, la jonction redevient continue. Sinon : (longue, None), inchangée."""
    from dataclasses import replace
    from statistics import median
    ref = {jour(b.ts): b.close for b in maj if b.close}
    rapports = [ref[jour(b.ts)] / b.close for b in longue if b.close and jour(b.ts) in ref]
    if not rapports:
        return longue, None
    f = median(rapports)
    if abs(f - 1.0) < ECART_MIN_FACTEUR or f <= 0:
        return longue, None
    if max(abs(r / f - 1.0) for r in rapports) > DISPERSION_MAX_FACTEUR:
        return longue, None
    return [replace(b, open=b.open * f, high=b.high * f, low=b.low * f, close=b.close * f)
            for b in longue], f
