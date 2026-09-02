"""Liquidité et structure « SMC/ICT » : SFP, BOS, CHoCH, zone OTE, order block.

SPÉCIFIÉ PAR L'UTILISATEUR (02/09), blocs 1-A et 1-B. Complète
`indicators/market_structure` (extrêmes protégés, échec d'enchère, tendance, POC), qui
fournit ici les pivots — une seule définition du pivot pour tout le dépôt.

CE QUE CES FONCTIONS SONT, ET CE QU'ELLES NE SONT PAS. Ce sont des définitions
GÉOMÉTRIQUES, exactes et testables : « la mèche dépasse le plus-haut des 50 barres et la
clôture revient dessous » est vérifiable ligne à ligne. Ce ne sont PAS des preuves
d'activité institutionnelle. Le vocabulaire du domaine (chasse aux stops, absorption,
smart money) décrit une INTENTION qu'un OHLCV ne contient pas. On code la géométrie ;
l'intention reste une hypothèse à mesurer.

DEUX PROPRIÉTÉS TENUES PARTOUT
  1. POINT-IN-TIME STRICT : une fonction évaluée à `i` ne lit que `barres[:i+1]`, et les
     pivots ne sont déclarés qu'une fois confirmés (décalage de `pivot` barres). Un
     pivot confirmé par les barres qui le suivent puis utilisé à SA date est un
     look-ahead — la version la plus courante et la plus coûteuse de ce biais.
  2. AGNOSTIQUE À L'UNITÉ DE TEMPS : rien ici ne suppose du 1D ou du 1H.

LIMITE DE DONNÉES, DITE PLUTÔT QUE CACHÉE. La base de ce dépôt est QUOTIDIENNE. Le
raffinement d'entrée en 1H/4H que décrit la spec n'est donc pas mesurable ici : ces
fonctions l'acceptent (passez-leur les barres que vous voulez), mais aucune donnée
intraday n'existe pour l'évaluer. Tant qu'elle n'existe pas, tout chiffre sur cette
jambe serait inventé — UNCALIBRATED.

RECOUVREMENT ASSUMÉ AVEC `strategies/institutional_price_action` (30/08), et il faut le
dire plutôt que le laisser découvrir. Ce plugin-là contient déjà des pivots confirmés,
des événements de structure, des zones FVG, des order blocks et un SFP — mais tous
PRIVÉS, calculés sur la série ENTIÈRE, et au service d'un objet `Signal`. Les fonctions
ci-dessous sont d'une autre nature : publiques, évaluées À UNE DATE `i`, renvoyant des
dictionnaires — c'est ce que réclame le harnais de mesure `research/flux_candidat`, qui
interroge un signal date par date et ne sait rien faire d'un objet `Signal`.

Les deux couches sont donc complémentaires, pas interchangeables. Il reste que SFP,
order block et cassure de structure existent maintenant en deux exemplaires dans le
dépôt : consolider `institutional_price_action` sur ces primitives est une dette
identifiée (P2 au TODO), pas un travail fait.

CE QUI EST RÉELLEMENT NOUVEAU ICI : la zone OTE (retracement 61,8-78,6 %), le CHoCH
distingué du BOS par le contexte de tendance, les niveaux BSL/SSL publics avec leur
filtre de volume, et leur composition en scénario complet (`continuation_ote`).

STATUT : SHADOW. Aucun appelant en production.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.indicators.market_structure import (
    pivots_indexes,
    tendance,
    volume_exceptionnel,
)

STATUT = "SHADOW_UNCALIBRATED"

FENETRE_LIQUIDITE = 50         # profondeur de recherche des sommets/creux majeurs
MULTIPLE_VOLUME_SFP = 1.5      # volume de la bougie de capture / moyenne 20
PIVOT = 5
OTE_DEBUT, OTE_FIN = 0.618, 0.786


@dataclass(frozen=True)
class Niveau:
    """Un niveau de liquidité et la barre qui l'a posé."""

    prix: float
    index: int


def liquidite(barres: list, i: int, fenetre: int = FENETRE_LIQUIDITE
              ) -> tuple[Niveau | None, Niveau | None]:
    """(BSL, SSL) : plus-haut et plus-bas des `fenetre` barres PRÉCÉDANT `i`.

    Strictement précédant : inclure la barre `i` dans sa propre référence rendrait tout
    franchissement impossible à détecter — le niveau se déplacerait avec la barre.
    """
    debut = max(0, i - fenetre)
    if i <= 0 or i >= len(barres) or i - debut < 5:
        return None, None
    fen = range(debut, i)
    jh = max(fen, key=lambda k: float(barres[k].high))
    jb = min(fen, key=lambda k: float(barres[k].low))
    return (Niveau(float(barres[jh].high), jh), Niveau(float(barres[jb].low), jb))


def sfp(barres: list, i: int, fenetre: int = FENETRE_LIQUIDITE,
        multiple: float = MULTIPLE_VOLUME_SFP) -> dict:
    """Swing Failure Pattern : la mèche prend la liquidité, la clôture la rend.

    Trois conditions, toutes lues sur `barres[:i+1]` :
      · la mèche de `i` dépasse le BSL (ou le SSL) des `fenetre` barres précédentes ;
      · la CLÔTURE de `i` réintègre la structure (repasse sous le BSL / au-dessus
        du SSL) ;
      · le volume de `i` dépasse `multiple` × la moyenne des 20 volumes précédents.

    Le filtre de volume est ce qui distingue un SFP d'une simple mèche : sans lui, la
    condition se déclenche sur toute barre un peu volatile près d'un extrême.
    """
    bsl, ssl = liquidite(barres, i, fenetre)
    if bsl is None or ssl is None:
        return {"statut": STATUT, "sfp": False, "sens": None}
    b = barres[i]
    haut, bas, close = float(b.high), float(b.low), float(b.close)
    fort = volume_exceptionnel(barres, i, multiple=multiple)
    if haut > bsl.prix and close < bsl.prix and fort:
        return {"statut": STATUT, "sfp": True, "sens": "short", "niveau": bsl.prix,
                "index_niveau": bsl.index, "extreme": haut, "volume_confirme": True}
    if bas < ssl.prix and close > ssl.prix and fort:
        return {"statut": STATUT, "sfp": True, "sens": "long", "niveau": ssl.prix,
                "index_niveau": ssl.index, "extreme": bas, "volume_confirme": True}
    return {"statut": STATUT, "sfp": False, "sens": None}


def bos(barres: list, i: int, pivot: int = PIVOT) -> dict:
    """Break of Structure : la CLÔTURE de `i` dépasse le dernier pivot CONFIRMÉ.

    La clôture et non la mèche : c'est la différence entre une cassure et un SFP, et
    confondre les deux fait prendre chaque chasse aux stops pour une continuation.
    """
    ih, ib = pivots_indexes(barres, i - 1, pivot) if i >= 1 else ([], [])
    if not ih and not ib:
        return {"statut": STATUT, "bos": False, "sens": None}
    close = float(barres[i].close)
    dernier_h = float(barres[ih[-1]].high) if ih else None
    dernier_b = float(barres[ib[-1]].low) if ib else None
    if dernier_h is not None and close > dernier_h:
        return {"statut": STATUT, "bos": True, "sens": "haussier",
                "niveau": dernier_h, "index_pivot": ih[-1]}
    if dernier_b is not None and close < dernier_b:
        return {"statut": STATUT, "bos": True, "sens": "baissier",
                "niveau": dernier_b, "index_pivot": ib[-1]}
    return {"statut": STATUT, "bos": False, "sens": None}


def choch(barres: list, i: int, pivot: int = PIVOT) -> dict:
    """Change of Character : une cassure CONTRE la tendance en cours.

    BOS et CHoCH sont la même géométrie ; seul le contexte les sépare. Une cassure
    haussière dans une tendance haussière est une continuation ; la même cassure dans
    une tendance baissière est un retournement. Sans le contexte, la distinction
    n'existe pas — et beaucoup d'implémentations la perdent.
    """
    c = bos(barres, i, pivot)
    if not c["bos"]:
        return {"statut": STATUT, "choch": False, "sens": None}
    t = tendance(barres, i - 1, pivot) if i >= 1 else "range"
    oppose = (t == "baissier" and c["sens"] == "haussier") or \
             (t == "haussier" and c["sens"] == "baissier")
    return {"statut": STATUT, "choch": bool(oppose),
            "sens": c["sens"] if oppose else None,
            "tendance_precedente": t, "niveau": c["niveau"]}


def impulsion(barres: list, i: int, pivot: int = PIVOT, sens: str = "haussier") -> dict:
    """Jambe d'impulsion qui a produit la cassure : du dernier creux au sommet
    (ou l'inverse).

    Renvoie les DEUX extrémités avec leurs indices, parce que la zone OTE et l'order
    block se calculent tous deux à partir de cette jambe et doivent parler de la même.
    """
    ih, ib = pivots_indexes(barres, i, pivot)
    if sens == "haussier":
        if not ib:
            return {"disponible": False}
        j0 = ib[-1]
        j1 = max(range(j0, i + 1), key=lambda k: float(barres[k].high))
        bas, haut = float(barres[j0].low), float(barres[j1].high)
    else:
        if not ih:
            return {"disponible": False}
        j0 = ih[-1]
        j1 = min(range(j0, i + 1), key=lambda k: float(barres[k].low))
        haut, bas = float(barres[j0].high), float(barres[j1].low)
    if haut <= bas or j1 <= j0:
        return {"disponible": False}
    return {"disponible": True, "sens": sens, "index_debut": j0, "index_fin": j1,
            "bas": bas, "haut": haut, "amplitude": haut - bas}


def zone_ote(imp: dict, debut: float = OTE_DEBUT, fin: float = OTE_FIN) -> dict:
    """Zone OTE : retracement 61,8 %-78,6 % de la jambe d'impulsion.

    Ces deux nombres ne sont pas mesurés, ils sont CONVENUS. Les traiter comme des
    paramètres à optimiser transformerait ce module en machine à surapprendre : on les
    fige donc à leur valeur de convention et on ne les balaie pas.
    """
    if not imp.get("disponible"):
        return {"disponible": False}
    bas, haut, ampl = imp["bas"], imp["haut"], imp["amplitude"]
    if imp["sens"] == "haussier":
        return {"disponible": True, "sens": "long", "haut_zone": haut - debut * ampl,
                "bas_zone": haut - fin * ampl}
    return {"disponible": True, "sens": "short", "bas_zone": bas + debut * ampl,
            "haut_zone": bas + fin * ampl}


def order_block(barres: list, imp: dict) -> dict:
    """Dernière bougie de sens OPPOSÉ avant l'impulsion — la définition usuelle de l'OB.

    On ne cherche l'OB QUE dans la jambe déclarée : le chercher sur tout l'historique
    en trouverait toujours un, ce qui reviendrait à n'imposer aucune condition.
    """
    if not imp.get("disponible"):
        return {"disponible": False}
    j0, j1 = imp["index_debut"], imp["index_fin"]
    veut_baissiere = imp["sens"] == "haussier"
    for k in range(j1, j0 - 1, -1):
        b = barres[k]
        baissiere = float(b.close) < float(b.open)
        if baissiere == veut_baissiere:
            return {"disponible": True, "index": k, "haut": float(b.high),
                    "bas": float(b.low), "ouverture": float(b.open),
                    "cloture": float(b.close)}
    return {"disponible": False}


def continuation_ote(barres: list, i: int, pivot: int = PIVOT) -> dict:
    """Scénario B complet : BOS, puis order block NON MITIGÉ imbriqué dans la zone OTE.

    « Non mitigé » = le prix n'est pas revenu dans l'order block depuis sa formation. Un
    OB déjà retraversé n'a plus la propriété qu'on lui prête ; ne pas le vérifier fait
    ressortir des zones que le marché a déjà consommées.
    """
    c = bos(barres, i, pivot)
    if not c["bos"]:
        return {"statut": STATUT, "autorise": False, "motif": "pas de BOS"}
    imp = impulsion(barres, i, pivot, sens=c["sens"])
    ote, ob = zone_ote(imp), order_block(barres, imp)
    if not ote.get("disponible") or not ob.get("disponible"):
        return {"statut": STATUT, "autorise": False,
                "motif": "impulsion/OB introuvable"}
    dans_zone = ob["bas"] <= ote["haut_zone"] and ob["haut"] >= ote["bas_zone"]
    mitige = _mitige(barres, ob, imp["index_fin"], i, c["sens"])
    return {"statut": STATUT, "autorise": bool(dans_zone and not mitige),
            "sens": "long" if c["sens"] == "haussier" else "short",
            "zone_ote": [round(ote["bas_zone"], 6), round(ote["haut_zone"], 6)],
            "order_block": [round(ob["bas"], 6), round(ob["haut"], 6)],
            "limite": round(ob["haut"] if c["sens"] == "haussier" else ob["bas"], 6),
            "mitige": bool(mitige),
            "motif": "" if dans_zone and not mitige
                     else ("OB déjà mitigé" if mitige else "OB hors zone OTE")}


def _mitige(barres: list, ob: dict, depuis: int, i: int, sens: str) -> bool:
    """Le prix est-il revenu dans l'order block depuis la fin de l'impulsion ?"""
    for k in range(max(depuis + 1, ob["index"] + 1), i + 1):
        if sens == "haussier" and float(barres[k].low) <= ob["haut"]:
            return True
        if sens == "baissier" and float(barres[k].high) >= ob["bas"]:
            return True
    return False
