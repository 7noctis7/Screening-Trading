"""Structure de marché : extrêmes « protégés », échec d'enchère, tendance, confluence.

SPÉCIFIÉ PAR L'UTILISATEUR (01/09), module 1. Détection algorithmique de structures de
prix et de volume, en remplacement d'indicateurs retardés.

DEUX PROPRIÉTÉS TENUES PARTOUT DANS CE FICHIER

1. POINT-IN-TIME STRICT. Une fonction évaluée à l'indice `i` ne lit que
   `barres[:i+1]`. Jamais une barre postérieure, jamais une moyenne calculée sur la
   série entière. C'est la seule garantie qui rend ces signaux utilisables en
   backtest sans fuite.

2. AGNOSTIQUE À L'UNITÉ DE TEMPS. Rien ici ne suppose 5 minutes ou 4 heures : on passe
   les barres qu'on veut. La spec vise du 5m/15m contre 1H/4H — un choix que ces
   fonctions permettent mais n'imposent pas.

LIMITE DE DONNÉES, À DIRE PLUTÔT QU'À CACHER. Le dépôt tourne sur des barres
QUOTIDIENNES et rebalance une fois par jour. Ces primitives fonctionnent sur des barres
quotidiennes, mais la lecture d'absorption que vise la spec (mèche + pic de volume comme
trace de capitaux institutionnels) est une lecture INTRADAY. Sur du quotidien, elle
décrit un fait de séance, pas un flux d'ordres. Le module est correct ; son pouvoir
prédictif à cette fréquence n'est pas établi et reste à mesurer.

STATUT : SHADOW. Aucun appelant en production.
"""

from __future__ import annotations

from dataclasses import dataclass

STATUT = "SHADOW_UNCALIBRATED"

PART_MECHE_MIN = 0.60          # mèche ≥ 60 % de la hauteur totale de la bougie
MULTIPLE_VOLUME = 1.5          # volume > 1,5 × moyenne des 20 précédents
FENETRE_VOLUME = 20


def _corps_et_meches(b) -> tuple[float, float, float]:
    """(hauteur totale, mèche basse, mèche haute) d'une bougie."""
    haut, bas = float(b.high), float(b.low)
    o, c = float(b.open), float(b.close)
    return haut - bas, min(o, c) - bas, haut - max(o, c)


def volume_exceptionnel(barres: list, i: int, multiple: float = MULTIPLE_VOLUME,
                        fenetre: int = FENETRE_VOLUME) -> bool:
    """Le volume de `i` dépasse-t-il `multiple` × la moyenne des `fenetre` PRÉCÉDENTES ?

    Les barres précédentes STRICTEMENT : inclure la barre courante dans sa propre
    moyenne de référence la dilue et rend le seuil plus facile à franchir quand le
    volume explose — l'inverse de ce qu'on veut détecter.
    """
    if i <= 0 or i >= len(barres):
        return False
    debut = max(0, i - fenetre)
    precedents = [float(b.volume) for b in barres[debut:i]]
    if len(precedents) < 2:
        return False
    moyenne = sum(precedents) / len(precedents)
    return moyenne > 0 and float(barres[i].volume) > multiple * moyenne


@dataclass(frozen=True)
class Extreme:
    """Un plus haut ou plus bas qualifié."""

    indice: int
    prix: float
    protege: bool
    part_meche: float
    volume_fort: bool

    def as_dict(self) -> dict:
        return {"indice": self.indice, "prix": round(self.prix, 6),
                "protege": self.protege, "part_meche": round(self.part_meche, 4),
                "volume_fort": self.volume_fort}


def bas_protege(barres: list, i: int, part_min: float = PART_MECHE_MIN) -> Extreme:
    """Plus bas « protégé » : mèche INFÉRIEURE ≥ 60 % de la bougie ET volume fort.

    Lecture visée : le prix est descendu puis a été repoussé dans la séance, avec du
    volume — trace d'une absorption par des acheteurs de taille.
    """
    b = barres[i]
    total, meche, _ = _corps_et_meches(b)
    part = meche / total if total > 0 else 0.0
    fort = volume_exceptionnel(barres, i)
    return Extreme(i, float(b.low), part >= part_min and fort, part, fort)


def haut_protege(barres: list, i: int, part_min: float = PART_MECHE_MIN) -> Extreme:
    """Symétrique : mèche SUPÉRIEURE ≥ 60 % et volume fort."""
    b = barres[i]
    total, _, meche = _corps_et_meches(b)
    part = meche / total if total > 0 else 0.0
    fort = volume_exceptionnel(barres, i)
    return Extreme(i, float(b.high), part >= part_min and fort, part, fort)


def echec_enchere(barres: list, i: int, k_volatilite: float = 1.5) -> dict:
    """Cassure SANS volume, rejetée immédiatement, avec accélération de volatilité.

    Trois conditions, toutes évaluées sur `i` et `i-1` uniquement :
      · la barre `i` dépasse l'extrême de `i-1` (cassure) ;
      · SANS volume exceptionnel (personne derrière) ;
      · et clôture revenue à l'intérieur de la barre `i-1` (rejet), avec une amplitude
        supérieure à `k_volatilite` × l'amplitude moyenne récente.
    """
    if i < FENETRE_VOLUME or i >= len(barres):
        return {"echec": False, "sens": None}
    prec, cur = barres[i - 1], barres[i]
    amplitudes = [float(b.high) - float(b.low) for b in barres[max(0, i - 20):i]]
    moy = sum(amplitudes) / len(amplitudes) if amplitudes else 0.0
    ampl = float(cur.high) - float(cur.low)
    accelere = moy > 0 and ampl > k_volatilite * moy
    sans_volume = not volume_exceptionnel(barres, i)
    haut = float(cur.high) > float(prec.high) and float(cur.close) < float(prec.high)
    bas = float(cur.low) < float(prec.low) and float(cur.close) > float(prec.low)
    if accelere and sans_volume and (haut or bas):
        return {"echec": True, "sens": "baissier" if haut else "haussier",
                "amplitude": round(ampl, 6), "amplitude_moyenne": round(moy, 6)}
    return {"echec": False, "sens": None}


def tendance(barres: list, i: int, pivot: int = 5) -> str:
    """« haussier », « baissier » ou « range » à l'indice `i`, par les pivots PASSÉS.

    Un pivot exige `pivot` barres de chaque côté pour être confirmé : on ne le déclare
    donc qu'une fois `pivot` barres écoulées APRÈS lui. Confirmer un pivot avec les
    barres qui le suivent puis l'utiliser à sa propre date serait un look-ahead — le
    décalage n'est pas une prudence, c'est la correction.
    """
    if i < 4 * pivot:
        return "range"
    hauts, bas = _pivots(barres, i, pivot)
    if len(hauts) < 2 or len(bas) < 2:
        return "range"
    if hauts[-1] > hauts[-2] and bas[-1] > bas[-2]:
        return "haussier"
    if hauts[-1] < hauts[-2] and bas[-1] < bas[-2]:
        return "baissier"
    return "range"


def pivots_indexes(barres: list, i: int, pivot: int) -> tuple[list[int], list[int]]:
    """INDICES des pivots CONFIRMÉS disponibles à `i` (décalés de `pivot` barres).

    Les indices, et pas seulement les prix : reconstruire une impulsion (d'où part une
    jambe, où elle finit) exige de savoir OÙ sont les pivots. `_pivots` en dérive les
    prix — une seule définition du pivot pour les deux usages, sinon elles divergent.

    EXTREMUM STRICT SUR LES VOISINS, et c'est une correction (02/09) : avec une
    comparaison large (`>=` sur la fenêtre, barre courante incluse), une série PLATE
    déclare un pivot à CHAQUE barre, puisque toutes sont ex æquo. La cassure de
    structure devenait alors trivialement vraie au moindre tick sur un titre peu
    liquide. On compare donc `barres[j]` à ses VOISINS seuls, strictement. Le prix
    d'une égalité exacte — un pivot perdu — va dans le sens prudent : moins de signaux.
    """
    hauts: list[int] = []
    bas: list[int] = []
    for j in range(pivot, i - pivot + 1):
        voisins = barres[j - pivot:j] + barres[j + 1:j + pivot + 1]
        if not voisins:
            continue
        h, b = float(barres[j].high), float(barres[j].low)
        if h > max(float(x.high) for x in voisins):
            hauts.append(j)
        if b < min(float(x.low) for x in voisins):
            bas.append(j)
    return hauts, bas


def _pivots(barres: list, i: int, pivot: int) -> tuple[list[float], list[float]]:
    """Pivots CONFIRMÉS disponibles à `i` (décalés de `pivot` barres)."""
    ih, ib = pivots_indexes(barres, i, pivot)
    return ([float(barres[j].high) for j in ih], [float(barres[j].low) for j in ib])


def point_de_controle(barres: list, i: int, fenetre: int = 60, bins: int = 24) -> float:
    """POC approché : prix du bin où le volume cumulé est le plus élevé.

    APPROXIMATION ASSUMÉE. Un vrai profil de volume demande le volume PAR PRIX, que des
    barres OHLCV ne portent pas. On répartit ici le volume de chaque barre sur son
    unique prix typique (H+L+C)/3. C'est grossier, et le nommer évite de lire ce chiffre
    comme un POC de carnet.
    """
    debut = max(0, i - fenetre + 1)
    fen = barres[debut:i + 1]
    if len(fen) < 5:
        return float(barres[i].close)
    typiques = [(float(b.high) + float(b.low) + float(b.close)) / 3.0 for b in fen]
    lo, hi = min(typiques), max(typiques)
    if hi <= lo:
        return typiques[-1]
    largeur = (hi - lo) / bins
    seaux = [0.0] * bins
    for t, b in zip(typiques, fen, strict=True):
        k = min(bins - 1, int((t - lo) / largeur))
        seaux[k] += float(b.volume)
    meilleur = max(range(bins), key=lambda k: seaux[k])
    return lo + (meilleur + 0.5) * largeur


def confluence(htf: list, i_htf: int, ltf: list, i_ltf: int) -> dict:
    """Autorisation d'entrée : tendance MAJEURE et signal MINEUR doivent s'accorder.

    Aucune entrée n'est autorisée si l'unité de temps majeure est en range : c'est le
    filtre qui supprime le plus de trades, et sur une stratégie à l'équilibre, supprimer
    des trades est le levier le plus fiable.
    """
    t = tendance(htf, i_htf)
    if t == "range":
        return {"statut": STATUT, "autorise": False, "sens": None, "tendance_htf": t,
                "motif": "unité de temps majeure en range — aucune entrée"}
    bas, haut = bas_protege(ltf, i_ltf), haut_protege(ltf, i_ltf)
    poc = point_de_controle(ltf, i_ltf)
    if t == "haussier" and bas.protege and float(ltf[i_ltf].low) <= poc:
        return {"statut": STATUT, "autorise": True, "sens": "long", "tendance_htf": t,
                "extreme": bas.as_dict(), "poc": round(poc, 6), "motif": ""}
    if t == "baissier" and haut.protege and float(ltf[i_ltf].high) >= poc:
        return {"statut": STATUT, "autorise": True, "sens": "short", "tendance_htf": t,
                "extreme": haut.as_dict(), "poc": round(poc, 6), "motif": ""}
    return {"statut": STATUT, "autorise": False, "sens": None, "tendance_htf": t,
            "motif": "pas d'extrême protégé dans la zone de volume"}
