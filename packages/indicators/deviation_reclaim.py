"""Déviation → reclaim → consolidation : la machine à états, sans note ni verdict.

CE QUE CE MODULE EST. Une définition GÉOMÉTRIQUE, exacte et testable, d'un motif en cinq
états : le prix passe sous une zone de support structurelle, balaie la liquidité, la
récupère par une CLÔTURE, puis accepte les prix au-dessus pendant plusieurs barres. Rien
d'autre. Chaque champ se vérifie ligne à ligne sur les barres.

CE QU'IL N'EST PAS, ET C'EST DÉLIBÉRÉ :
  · il ne note pas — aucun score 0-100. Des poids choisis à la main (20 % pour la zone,
    15 % pour le sweep…) transforment une opinion en chiffre, ce qui la rend plus dure à
    réfuter sans la rendre plus vraie. Le dépôt a déjà refusé une règle de régime dont
    le t était significatif partout et la médiane négative (ADR-0145) ;
  · il ne recommande rien — pas d'« EXECUTE ». Un composant non certifié qui dit
    d'acheter est un P0 (`vault/15_CERTIFICATION.md`) ;
  · il ne calcule pas de reward/risk comme FILTRE. Cible et résistance sont choisies par
    la même analyse qui calcule le ratio : un tel ratio ne filtre rien, il mesure sa
    propre générosité. Les niveaux sont publiés ; leur exploitation est un autre sujet.

DEUX PROPRIÉTÉS TENUES, comme dans `liquidite_ict` :
  1. POINT-IN-TIME STRICT : `etat(barres, i)` ne lit que `barres[:i+1]`, et les pivots
     ne sont déclarés qu'une fois CONFIRMÉS (décalage de `pivot` barres). Un pivot
     confirmé par les barres qui le suivent puis daté à SA barre est la forme de
     look-ahead la plus courante et la plus coûteuse.
  2. AGNOSTIQUE À L'UNITÉ DE TEMPS : rien ici ne suppose du 1D.

CE QUI N'EST PAS MESURABLE AUJOURD'HUI, ET DOIT ÊTRE DIT. La spec d'origine demande un
timeframe d'exécution 4H. La base de prix de ce dépôt est QUOTIDIENNE — le fournisseur
mappe même « 4h » sur « 1h », et `vault/03_TODO.md` porte déjà le manque en P2. Le
Weekly se dérive légitimement du Daily ; le 4H, non. Toute jambe 4H serait UNCALIBRATED,
et ce module ne prétend donc pas la traiter.

RECOUVREMENT ASSUMÉ avec `liquidite_ict.sfp`, et il faut le dire. Le SFP est le cas
PARTICULIER où déviation et reclaim tiennent dans UNE barre (la mèche prend la
liquidité, la clôture la rend). Ici les deux peuvent être séparés de plusieurs barres :
c'est un motif plus large, dont le SFP est un sous-ensemble. `sfp_confirme` le signale
quand les deux coïncident — ce qui permet de MESURER si le motif large apporte quelque
chose au-delà de la primitive qui existait déjà.
"""

from __future__ import annotations

from packages.indicators.market_structure import pivots_indexes

SEARCHING = "SEARCHING"
DEVIATION_DETECTED = "DEVIATION_DETECTED"
RECLAIM_CONFIRMED = "RECLAIM_CONFIRMED"
CONSOLIDATION_CONFIRMED = "CONSOLIDATION_CONFIRMED"
EXPANSION_CONFIRMED = "EXPANSION_CONFIRMED"

ETATS = (SEARCHING, DEVIATION_DETECTED, RECLAIM_CONFIRMED,
         CONSOLIDATION_CONFIRMED, EXPANSION_CONFIRMED)

PIVOT = 5                 # même définition que `market_structure`
TOLERANCE_ZONE = 0.02     # deux creux à moins de 2 % l'un de l'autre forment une zone
DELAI_RECLAIM = 10        # au-delà, une reprise n'est plus une déviation mais un rebond
BARRES_CONSOLIDATION = 3  # minimum d'acceptation au-dessus de la zone
MIN_REACTIONS = 2         # « au moins 2 réactions antérieures » — la zone, pas un creux


def pivots_causaux(barres: list, pivot: int = PIVOT) -> tuple[list[int], list[int]]:
    """TOUS les pivots de la série, à filtrer ensuite par leur date de CONFIRMATION.

    POURQUOI CETTE FONCTION EXISTE, ET POURQUOI ELLE NE TRICHE PAS. `pivots_indexes`
    rescanne la série à chaque barre : O(n²) par titre, soit ~7 millions d'opérations
    pour un historique de 2 600 jours — et 199 titres rendent le banc inexécutable.

    Un pivot en `j` est confirmé en `j + pivot` et ne dépend QUE de `barres[j-pivot ..
    j+pivot]`. Le précalculer sur la série entière puis ne garder que ceux vérifiant
    `j + pivot <= i` donne donc EXACTEMENT le même ensemble qu'un rescan à `i` — c'est
    une optimisation, pas un assouplissement, et un test le vérifie barre par barre.
    Sans cette égalité démontrée, précalculer serait exactement la porte par laquelle le
    look-ahead entre.
    """
    return pivots_indexes(barres, len(barres) - 1 + pivot, pivot)


def _disponibles(pivots: tuple[list[int], list[int]], i: int,
                 pivot: int) -> tuple[list[int], list[int]]:
    """Les pivots CONFIRMÉS à `i` : ceux dont la confirmation tombe au plus tard là."""
    hauts, bas = pivots
    return ([j for j in hauts if j + pivot <= i], [j for j in bas if j + pivot <= i])


def _rel(a: float, b: float) -> float:
    """Écart RELATIF. En absolu, on mélangerait un titre à 5 $ et un à 500 $."""
    return abs(a - b) / max(1e-9, abs(b))


def zone_support(barres: list, i: int, pivot: int = PIVOT,
                 tolerance: float = TOLERANCE_ZONE,
                 pivots: tuple[list[int], list[int]] | None = None) -> dict | None:
    """La zone de support structurelle la plus récente, ou None.

    Une zone n'est pas un creux : c'est un AGRÉGAT de creux confirmés proches les uns
    des autres. Exiger `MIN_REACTIONS` creux distingue un support d'un accident — et
    empêche le motif de se déclencher sur n'importe quel bas local.
    """
    _, bas = (_disponibles(pivots, i, pivot) if pivots is not None
              else pivots_indexes(barres, i, pivot))
    if len(bas) < MIN_REACTIONS:
        return None
    prix = [(j, float(barres[j].low)) for j in bas]
    # ON N'ANCRE PAS SUR LE DERNIER CREUX, et c'est un correctif de conception. Une fois
    # la déviation confirmée comme pivot, elle DEVIENT le creux le plus récent — et,
    # isolée, elle ne rassemble personne : la zone dont le prix venait de dévier
    # disparaissait donc à l'instant précis où le motif devenait intéressant. On essaie
    # chaque ancre de la plus récente à la plus ancienne, et on retient la première qui
    # réunit assez de réactions. Le creux isolé du sweep est ainsi sauté de lui-même,
    # sans règle ad hoc pour l'exclure.
    for rang in range(len(prix) - 1, -1, -1):
        ancre = prix[rang][1]
        membres = [(j, p) for j, p in prix if _rel(p, ancre) <= tolerance]
        if len(membres) < MIN_REACTIONS:
            continue
        lows = [p for _, p in membres]
        return {"low": min(lows), "high": max(lows), "reactions": len(membres),
                "index_reactions": [j for j, _ in membres]}
    return None


def _deviation(barres: list, i: int, ksz: dict, depuis: int,
               duree_max: int) -> dict | None:
    """L'ÉPISODE le plus récent passé sous la zone : sa dernière barre et son EXTRÊME.

    On exige un passage sous `KSZ_LOW` ET sous le plus bas des creux qui FORMENT la
    zone : sans cette seconde condition, une mèche à l'intérieur de la zone compterait
    comme une prise de liquidité alors qu'elle n'a balayé aucun stop sous les creux.

    UNE DÉVIATION EST BRÈVE, PAR DÉFINITION. « Une chute prolongée sous la zone sans
    réaction rapide n'est PAS une déviation : c'est une cassure baissière. » Borner le
    seul délai de reclaim ne suffit pas : vingt barres passées sous la zone puis une
    clôture au-dessus satisfaisaient le délai — mesuré par le test, qui a trouvé
    CONSOLIDATION_CONFIRMED sur une cassure franche. C'est la DURÉE DE L'ÉPISODE qu'il
    faut borner.

    UN ÉPISODE, PAS UNE BARRE, et ce n'est pas un détail de forme. L'invalidation se
    place sous l'extrême de la déviation ; si on ne retenait que la DERNIÈRE barre sous
    la zone, un sweep à 95 suivi d'une barre à 97 donnerait une invalidation à 97 —
    un stop plus serré que le creux réellement balayé, donc un reward/risk flatté par
    construction. On remonte donc l'épisode contigu et on prend son minimum.
    """
    plancher = min(float(barres[j].low) for j in ksz["index_reactions"])

    def sous(j: int) -> bool:
        bas = float(barres[j].low)
        return bas < ksz["low"] and bas < plancher

    fin = next((j for j in range(i, depuis - 1, -1) if sous(j)), None)
    if fin is None:
        return None
    debut = fin
    while debut - 1 >= depuis and sous(debut - 1):
        debut -= 1
    if fin - debut + 1 > duree_max:
        return None                       # cassure baissière, pas déviation absorbée
    extreme = min(float(barres[j].low) for j in range(debut, fin + 1))
    return {"index": fin, "index_debut": debut, "extreme": extreme,
            "barres": fin - debut + 1,
            "profondeur_pct": round((ksz["low"] - extreme) / ksz["low"] * 100, 4)}


def _reclaim(barres: list, i: int, ksz: dict, dev: dict,
             delai: int) -> dict | None:
    """Première CLÔTURE au-dessus de `KSZ_LOW` après la déviation, dans le délai.

    Une mèche ne suffit pas : c'est la règle explicite de la spec, et c'est la même
    distinction que `bos` fait entre une cassure et un SFP. Passé `delai` barres sous la
    zone, ce n'est plus une déviation absorbée — c'est une cassure baissière, et la
    remontée qui suit est un autre motif.
    """
    for k in range(dev["index"] + 1, min(i, dev["index"] + delai) + 1):
        if float(barres[k].close) > ksz["low"]:
            return {"index": k, "fort": float(barres[k].close) > ksz["high"],
                    "cloture": float(barres[k].close)}
    return None


def _atr(barres: list, debut: int, fin: int) -> float:
    """Amplitude moyenne, bornes incluses. Compare deux fenêtres, ne trade rien."""
    fen = barres[max(0, debut):fin + 1]
    if not fen:
        return 0.0
    return sum(float(b.high) - float(b.low) for b in fen) / len(fen)


def _consolidation(barres: list, i: int, ksz: dict, rec: dict,
                   invalidation: float, minimum: int) -> dict | None:
    """Acceptation des prix après le reclaim : aucune clôture sous l'invalidation.

    Les mèches sous la zone sont tolérées — la spec le demande, et c'est cohérent avec
    la règle d'invalidation en CLÔTURE. Ce qui ne l'est pas : une clôture sous le niveau
    d'invalidation, qui fabriquerait un nouveau creux structurel.
    """
    barres_apres = i - rec["index"]
    if barres_apres < minimum:
        return None
    fen = barres[rec["index"]:i + 1]
    if any(float(b.close) < invalidation for b in fen):
        return None
    tient = sum(1 for b in fen if float(b.close) >= ksz["low"]) / len(fen)
    avant = _atr(barres, rec["index"] - len(fen), rec["index"] - 1)
    apres = _atr(barres, rec["index"], i)
    return {"barres": barres_apres, "part_au_dessus": round(tient, 4),
            "contraction": bool(avant > 0 and apres < avant),
            "atr_avant": round(avant, 6), "atr_apres": round(apres, 6)}


def _resistances(barres: list, i: int, pivot: int, plancher: float,
                 pivots: tuple[list[int], list[int]] | None = None) -> dict:
    """Première résistance confirmée au-dessus du prix, et sommet majeur de la fenêtre.

    Aucune cible inventée : les deux sortent de pivots CONFIRMÉS. Si la structure n'en
    fournit pas, on renvoie None — ce que la spec appelle « ne pas définir une cible
    arbitraire pour améliorer le ratio ».
    """
    hauts, _ = (_disponibles(pivots, i, pivot) if pivots is not None
                else pivots_indexes(barres, i, pivot))
    prix = [float(barres[j].high) for j in hauts]
    au_dessus = sorted(p for p in prix if p > plancher)
    return {"confirmation": au_dessus[0] if au_dessus else None,
            "macro": max(prix) if prix else None}


def etat(barres: list, i: int, *, pivot: int = PIVOT,
         tolerance: float = TOLERANCE_ZONE, delai: int = DELAI_RECLAIM,
         consolidation_min: int = BARRES_CONSOLIDATION,
         fenetre: int = 120,
         pivots: tuple[list[int], list[int]] | None = None) -> dict:
    """L'état du motif à la barre `i`, en ne lisant que `barres[:i+1]`.

    Renvoie toujours un dict : `etat` vaut `SEARCHING` quand rien ne tient, avec son
    motif. Aucun champ n'est deviné — un niveau absent de la structure vaut `None`.
    """
    vide = {"etat": SEARCHING, "zone": None, "deviation": None, "reclaim": None,
            "consolidation": None, "invalidation": None, "confirmation": None,
            "macro": None, "sfp_confirme": False, "motif": ""}
    if i < pivot * 2 + consolidation_min or i >= len(barres):
        return {**vide, "motif": "historique insuffisant"}
    ksz = zone_support(barres, i, pivot, tolerance, pivots)
    if not ksz:
        return {**vide, "motif": f"aucune zone à {MIN_REACTIONS} réactions"}
    dev = _deviation(barres, i, ksz, max(0, i - fenetre), delai)
    if not dev:
        return {**vide, "zone": ksz,
                "motif": "aucun passage BREF sous la zone (ou cassure "
                         f"durable de plus de {delai} barres)"}
    rec = _reclaim(barres, i, ksz, dev, delai)
    if not rec:
        return {**vide, "zone": ksz, "deviation": dev, "etat": DEVIATION_DETECTED,
                "invalidation": dev["extreme"],
                "motif": f"pas de clôture au-dessus de la zone en {delai} barres"}
    invalidation = dev["extreme"]
    conso = _consolidation(barres, i, ksz, rec, invalidation, consolidation_min)
    niveaux = _resistances(barres, i, pivot, float(barres[i].close), pivots)
    base = {**vide, "zone": ksz, "deviation": dev, "reclaim": rec,
            "invalidation": invalidation, "confirmation": niveaux["confirmation"],
            "macro": niveaux["macro"],
            "sfp_confirme": rec["index"] == dev["index"]}
    if not conso:
        return {**base, "etat": RECLAIM_CONFIRMED,
                "motif": f"acceptation < {consolidation_min} barres, ou clôture sous "
                         "l'invalidation"}
    cr = niveaux["confirmation"]
    if cr is not None and float(barres[i].close) > cr:
        return {**base, "consolidation": conso, "etat": EXPANSION_CONFIRMED,
                "motif": "clôture au-dessus de la résistance de confirmation"}
    return {**base, "consolidation": conso, "etat": CONSOLIDATION_CONFIRMED,
            "motif": "acceptation confirmée au-dessus de la zone"}
