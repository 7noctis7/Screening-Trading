"""Garde-fous de portefeuille swing : régime de marché et plafond de corrélation.

SPÉCIFIÉ PAR L'UTILISATEUR (02/09), bloc 3 §3. Les deux autres tiers du bloc existent
déjà et ne sont PAS redupliqués ici :
  · dimensionnement 1R et réduction géométrique -4R → `risk/ddm` (MachineDDM) ;
  · stop structurel/ATR                            → `risk/atr_stops`.
Ce module n'ajoute que ce qui manquait vraiment.

CE QUE CES DEUX RÈGLES ONT EN COMMUN. Ni l'une ni l'autre ne cherche un gain : elles
REFUSENT des positions. C'est leur intérêt — sur une stratégie proche de l'équilibre,
supprimer des trades corrélés est plus fiable que d'en ajouter des bons, parce que le
premier effet est arithmétique et le second hypothétique.

CE QUE LA LIMITE DE CORRÉLATION MESURE VRAIMENT. Trois positions corrélées à 0,70 ne
sont pas trois positions : le nombre effectif vaut N/(1+(N-1)·rho), soit ~1,4 ici. La
règle « au plus 3 lignes au-dessus de 0,70 » est donc un plafond sur la CONCENTRATION
DÉGUISÉE, pas sur le nombre de lignes affichées. Le compte réel de ce dépôt en est
l'illustration : N effectif 1,5 pour un portefeuille qui montre bien plus de lignes.

FENÊTRE DE 30 JOURS : C'EST COURT, ET C'EST UN CHOIX QUI COÛTE. Trente points donnent
une corrélation dont l'erreur-type avoisine 0,19 sous l'hypothèse nulle — une paire
mesurée à 0,70 pourrait valoir 0,50 comme 0,85. La fenêtre courte réagit vite aux
régimes ; elle se paie en bruit. On renvoie donc le nombre de points utilisés, pour que
le lecteur sache sur quoi la décision repose.

STATUT : SHADOW. Aucun appelant en production.
"""

from __future__ import annotations

import math

STATUT = "SHADOW_UNCALIBRATED"

FENETRE_CORRELATION = 30
SEUIL_CORRELATION = 0.70
MAX_LIGNES_CORRELEES = 3
FENETRE_REGIME = 200
REDUCTION_BEAR = 0.50


def _sma(valeurs: list[float], n: int) -> float | None:
    return sum(valeurs[-n:]) / n if len(valeurs) >= n else None


def regime_marche(closes_reference, fenetre: int = FENETRE_REGIME,
                  reduction: float = REDUCTION_BEAR) -> dict:
    """L'indice est-il sous sa moyenne mobile `fenetre` ? Facteur d'exposition.

    LE FILTRE LE PLUS DOCUMENTÉ DE LA LITTÉRATURE, ET LE PLUS SUREXPLOITÉ. La MM200 ne
    prédit rien : elle décrit. Son effet établi porte sur le RISQUE (elle coupe la
    participation aux marchés baissiers prolongés), pas sur le rendement — ces deux
    lectures sont souvent confondues, et seule la première résiste hors échantillon.

    Le franchissement se lit sur la DERNIÈRE clôture connue, jamais sur une moyenne
    calculée avec des barres futures : la moyenne s'arrête à la même barre que le prix.
    """
    closes = [float(c) for c in (closes_reference or []) if c is not None]
    mm = _sma(closes, fenetre)
    if mm is None:
        return {"statut": STATUT, "disponible": False, "facteur_long": 1.0,
                "motif": f"moins de {fenetre} clôtures — régime indéterminé, "
                         "aucune réduction appliquée"}
    dernier = closes[-1]
    sous = dernier < mm
    return {"statut": STATUT, "disponible": True, "regime": "bear" if sous else "bull",
            "facteur_long": reduction if sous else 1.0,
            "cloture": round(dernier, 6), "mm": round(mm, 6),
            "ecart_pct": round((dernier / mm - 1.0) * 100.0, 2), "n": len(closes)}


def _correlation(a: list[float], b: list[float]) -> float | None:
    """Pearson sur deux séries DÉJÀ appariées. `None` si l'appariement est douteux.

    On refuse des longueurs différentes plutôt que de recadrer sur `[-m:]` : ce
    recadrage silencieux est l'origine de trois bugs d'empilement dans ce dépôt.
    """
    n = len(a)
    if n < 10 or len(b) != n:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / math.sqrt(va * vb)


def _rendements(closes: list[float], fenetre: int) -> list[float]:
    c = [float(x) for x in closes if x is not None and float(x) > 0]
    r = [c[i] / c[i - 1] - 1.0 for i in range(1, len(c))]
    return r[-fenetre:]


def grappes_correlees(rendements_par_symbole: dict[str, list[float]],
                      seuil: float = SEUIL_CORRELATION) -> list[list[str]]:
    """Groupes de symboles reliés par au moins une paire au-dessus de `seuil`.

    Regroupement par LIAISON SIMPLE (transitif) : si A~B et B~C, les trois comptent
    comme un même risque même si A et C ne se ressemblent pas directement. C'est le
    choix prudent — l'inverse laisserait passer une chaîne de positions dont chaque
    maillon est « acceptable » alors que l'ensemble ne l'est pas.
    """
    syms = sorted(rendements_par_symbole)
    parent = {s: s for s in syms}

    def racine(s: str) -> str:
        while parent[s] != s:
            parent[s] = parent[parent[s]]
            s = parent[s]
        return s

    for i, a in enumerate(syms):
        for b in syms[i + 1:]:
            rho = _correlation(rendements_par_symbole[a], rendements_par_symbole[b])
            if rho is not None and rho > seuil:
                parent[racine(a)] = racine(b)
    grappes: dict[str, list[str]] = {}
    for s in syms:
        grappes.setdefault(racine(s), []).append(s)
    return [sorted(g) for g in grappes.values() if len(g) > 1]


def filtrer_correlation(candidats: list[str],
                        closes_par_symbole: dict[str, list[float]],
                        fenetre: int = FENETRE_CORRELATION,
                        seuil: float = SEUIL_CORRELATION,
                        maximum: int = MAX_LIGNES_CORRELEES) -> dict:
    """Au plus `maximum` lignes par grappe corrélée. Renvoie retenus, refusés, motifs.

    L'ORDRE DE `candidats` EST L'ORDRE DE PRIORITÉ, et l'appelant en est responsable :
    ce module ne classe pas, il coupe. Trancher par ordre alphabétique — ce que ferait
    un `set` — reviendrait à laisser le hasard décider quelle conviction survit.

    UN TITRE À HISTORIQUE TROP COURT EST REFUSÉ, PAS LAISSÉ PASSER. Le retenir « faute
    de mesure » lui offrirait une porte de sortie : il suffirait d'un titre récent pour
    contourner le plafond. On refuse dans le sens prudent et on le DIT, plutôt que
    d'accepter en silence. Les séries doivent partager le même calendrier — les
    apparier ici, sur des longueurs différentes, recréerait le bug d'empilement.
    """
    rends = {s: _rendements(closes_par_symbole.get(s, []), fenetre) for s in candidats}
    rends = {s: r for s, r in rends.items() if len(r) == fenetre}
    sans_donnees = [s for s in candidats if s not in rends]
    grappes = grappes_correlees(rends, seuil)
    appartenance = {s: i for i, g in enumerate(grappes) for s in g}
    compte: dict[int, int] = {}
    retenus, refuses = [], []
    for s in candidats:
        if s in sans_donnees:
            refuses.append({"symbole": s, "grappe": [],
                            "motif": f"moins de {fenetre} rendements — "
                                     "corrélation non mesurable, refus prudent"})
            continue
        g = appartenance.get(s)
        if g is None:
            retenus.append(s)
            continue
        compte[g] = compte.get(g, 0) + 1
        if compte[g] <= maximum:
            retenus.append(s)
        else:
            refuses.append({
                "symbole": s, "grappe": sorted(grappes[g]),
                "motif": f"plus de {maximum} lignes corrélées > {seuil:.2f}"})
    return {"statut": STATUT, "retenus": retenus, "refuses": refuses,
            "grappes": grappes, "sans_donnees": sans_donnees,
            "n_points": fenetre if rends else 0,
            "seuil": seuil, "fenetre": fenetre}


def exposition_autorisee(closes_reference, candidats: list[str],
                         closes_par_symbole: dict[str, list[float]],
                         **kw) -> dict:
    """Les deux garde-fous appliqués ensemble : régime PUIS corrélation.

    Dans cet ordre parce qu'ils ne font pas la même chose : le régime module la TAILLE
    de l'exposition longue, la corrélation coupe des LIGNES. Les inverser donnerait le
    même ensemble de titres mais rendrait le facteur illisible.
    """
    reg = regime_marche(closes_reference)
    filt = filtrer_correlation(candidats, closes_par_symbole, **kw)
    return {"statut": STATUT, "facteur_long": reg["facteur_long"], "regime": reg,
            "correlation": filt, "retenus": filt["retenus"]}
