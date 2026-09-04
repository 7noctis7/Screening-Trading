"""Fenêtre commune d'un panel de séries — corrige la tyrannie de `min(len)`.

Le motif `L = min(len(data[s]) for s in syms)` était répliqué dans quinze backtests. Il aligne
les séries par la fin (`[-L:]`), ce qui est correct, mais laisse la série la PLUS COURTE fixer la
profondeur de TOUT le panel : une introduction en bourse récente ramène dix ans d'historique à
treize mois pour les 900 autres titres. Constat du 24/08 sur données réelles : 929 titres,
`QUANT_HISTORY_DAYS=4015`, et le preset ne produisait que **7 rebalancements** — un Sharpe
« 1,24 » calculé sur sept points, dont les leviers de risque ne pouvaient même pas se déclencher
(l'overlay exige `len(port) >= 10`).

Règle retenue : la fenêtre la plus LONGUE couverte par au moins `couverture` des noms éligibles ;
les noms trop courts sont écartés du panel et le rapport le dit. C'est la même règle que la grille
de dates d'`alpha_lab` (80 % de couverture) — une seule convention dans le projet.

Ce filtre est un filtre d'ANCIENNETÉ DE COTATION, pas un filtre de performance : il ne regarde
jamais les prix, seulement les longueurs. Il n'introduit donc pas de biais du survivant
supplémentaire (les délistés, eux, relèvent de `packages/data/survivorship`).
"""

from __future__ import annotations

COUVERTURE_DEFAUT = 0.80
MIN_NOMS = 5


def fenetre_commune(data: dict, syms: list[str], couverture: float = COUVERTURE_DEFAUT,
                    min_noms: int = MIN_NOMS) -> tuple[list[str], int, dict]:
    """(noms retenus, longueur commune L, diagnostic).

    `couverture=1.0` reproduit exactement l'ancien comportement (`min`), pour comparaison.
    Le diagnostic est fait pour être PUBLIÉ : `n_steps` réels et noms écartés sont la seule
    façon de distinguer « levier rejeté » de « levier jamais déclenché ».
    """
    longueurs = sorted((len(data[s]) for s in syms), reverse=True)
    if not longueurs:
        return [], 0, {"available": False, "n_eligibles": 0}
    cible = max(min_noms, int(round(max(0.0, min(1.0, couverture)) * len(longueurs))))
    L = longueurs[min(cible, len(longueurs)) - 1]
    retenus = [s for s in syms if len(data[s]) >= L]
    diag = {"available": True, "n_eligibles": len(syms), "n_retenus": len(retenus),
            "n_ecartes": len(syms) - len(retenus), "L": L,
            "L_min": longueurs[-1], "L_max": longueurs[0], "couverture": round(couverture, 3),
            "gain_vs_min": round(L / longueurs[-1], 2) if longueurs[-1] else None}
    return retenus, L, diag


def _jour(barre) -> str:
    """Clé de date d'une barre, à la journée. Deux sources peuvent horodater la même séance à
    des heures différentes (clôture locale, UTC) : comparer les instants créerait des dates
    distinctes pour une même séance."""
    ts = getattr(barre, "ts", None)
    if ts is None:
        return ""
    d = getattr(ts, "date", None)
    return (d().isoformat() if callable(d) else str(ts)[:10])


def aligner_par_date(data: dict, syms: list[str], couverture: float = COUVERTURE_DEFAUT,
                     min_noms: int = MIN_NOMS) -> tuple[list[str], list[str], "object", dict]:
    """Aligne les séries PAR DATE. Renvoie (noms, dates, matrice n×T, diagnostic).

    POURQUOI CE MODULE EXISTE. `fenetre_commune` corrige la profondeur du panel mais garde
    l'alignement POSITIONNEL : on prend les `L` dernières barres de chaque série et on les
    empile. Cela suppose que toutes les séries se terminent le même jour — vrai entre titres
    encore cotés, **faux par construction pour un délisté**, dont la dernière barre est sa date
    de radiation. Empiler positionnellement collerait ses prix de 2020 sur les dates de 2026.
    C'est ce qui rend aujourd'hui le biais du survivant NON MESURABLE.

    La grille de dates est celle couverte par au moins `couverture` des noms — même convention
    que `fenetre_commune`, une seule règle dans le projet. Les cases sans cotation valent NaN :
    un titre pas encore introduit, ou déjà radié, n'a pas un prix nul, il n'a **pas de prix**.
    Écrire zéro produirait un rendement de −100 % le jour de la radiation.

    PROPRIÉTÉ D'ÉQUIVALENCE, et c'est elle qui rend la migration sûre : quand toutes les séries
    partagent le même calendrier, la matrice produite est identique à l'empilement positionnel.
    Les chiffres ne bougent donc QUE là où l'alignement positionnel était faux.
    """
    import numpy as np

    if not syms:
        return [], [], np.empty((0, 0)), {"available": False, "n_eligibles": 0}
    par_sym = {}
    for s in syms:
        serie = {}
        for b in data.get(s) or []:
            j = _jour(b)
            if j and getattr(b, "close", None):
                serie[j] = float(b.close)
        if serie:
            par_sym[s] = serie
    if len(par_sym) < min_noms:
        return [], [], np.empty((0, 0)), {"available": False, "n_eligibles": len(par_sym)}

    from collections import Counter
    compte = Counter(j for serie in par_sym.values() for j in serie)
    seuil = max(1, int(round(max(0.0, min(1.0, couverture)) * len(par_sym))))
    dates = sorted(j for j, n in compte.items() if n >= seuil)
    if not dates:
        return [], [], np.empty((0, 0)), {"available": False, "n_eligibles": len(par_sym)}

    noms = sorted(par_sym)
    A = np.full((len(noms), len(dates)), np.nan)
    for i, s in enumerate(noms):
        serie = par_sym[s]
        for t, j in enumerate(dates):
            v = serie.get(j)
            if v is not None:
                A[i, t] = v
    couvert = np.isfinite(A).mean(axis=1)
    diag = {"available": True, "n_eligibles": len(syms), "n_retenus": len(noms),
            "n_dates": len(dates), "debut": dates[0], "fin": dates[-1],
            "couverture": round(couverture, 3),
            "taux_remplissage": round(float(np.isfinite(A).mean()), 4),
            # Séries qui ne couvrent pas toute la grille : introduites en cours de route, ou
            # radiées. C'est exactement la population que l'alignement positionnel écrasait.
            "n_partielles": int((couvert < 1.0).sum())}
    return noms, dates, A, diag


def apparier_deux_series(a: list[float], dates_a: list[str],
                         b: list[float], dates_b: list[str]
                         ) -> tuple[list[float], list[float], list[str]]:
    """Deux courbes venues de CALENDRIERS DIFFÉRENTS, appariées par date.

    QUATRIÈME OCCURRENCE DE L'EMPILEMENT POSITIONNEL, et la plus visible (04/09).
    `compute_attribution` comparait la courbe du preset (calendrier de l'univers
    négociable) à celle de QQQ (calendrier des indices) en prenant les `n` dernières
    valeurs de chacune. Deux séries décalées d'une poignée de séances ne sont pas
    corrélées : le résultat publié était **bêta 0,006 et corrélation 0,008** pour un
    portefeuille long-only d'actions américaines. Un chiffre absurde, affiché sans que
    rien ne le signale — c'est la marque de ce bug : il ne plante pas, il ment.

    `aligner_par_date` traite N séries d'un même dictionnaire de barres ; il manquait le
    cas à DEUX séries déjà réduites à (valeurs, dates). Une seule règle d'alignement
    dans le projet, deux points d'entrée selon la forme des données.

    Renvoie les deux séries restreintes à l'INTERSECTION des dates, dans l'ordre
    chronologique, plus ces dates. Intersection vide → trois listes vides : l'appelant
    doit refuser de conclure, pas retomber sur un appariement positionnel."""
    par_a = dict(zip(dates_a, a, strict=False))
    par_b = dict(zip(dates_b, b, strict=False))
    communes = sorted(set(par_a) & set(par_b))
    return ([par_a[d] for d in communes], [par_b[d] for d in communes], communes)


def dernier_connu(A, t: int) -> "object":
    """Dernier prix CONNU de chaque titre à la date `t` (report en avant du passé seulement).

    Sert à valoriser une ligne dont la cotation s'arrête en cours de période : on la solde au
    dernier cours observé. C'est une approximation OPTIMISTE pour une faillite — le dernier
    cours coté d'une société en liquidation est rarement zéro — et elle doit être lue comme
    telle : le biais du survivant ainsi mesuré est un MINORANT, pas la vérité.

    Neutre sur une matrice complète : renvoie exactement `A[:, t]`.
    """
    import numpy as np

    fenetre = A[:, : t + 1]
    fini = np.isfinite(fenetre)
    idx = np.where(fini.any(axis=1), fini.shape[1] - 1 - np.argmax(fini[:, ::-1], axis=1), -1)
    out = np.full(A.shape[0], np.nan)
    ok = idx >= 0
    out[ok] = fenetre[np.arange(A.shape[0])[ok], idx[ok]]
    return out


def aligner_sans_trous(data: dict, syms: list[str],
                       min_noms: int) -> tuple[list[str], list[str], "object"]:
    """Grille alignée par DATE et garantie SANS NaN. Renvoie (noms, dates, matrice n×T).

    POURQUOI UNE RÈGLE DE PLUS. `aligner_par_date` produit une matrice avec des NaN là où un
    titre n'est pas coté ; c'est correct pour un backtest qui sait les traiter. Mais la courbe du
    tableau de bord, le journal de trades et le LEDGER font de la comptabilité parts/cash : un
    NaN y produirait un P&L **faux** plutôt qu'une erreur visible. On préfère donc une grille plus
    étroite et sûre à une grille large et piégeuse.

    Méthode : garder les `min_noms` séries les mieux couvertes, puis restreindre aux dates où
    TOUTES sont cotées. L'intersection de calendriers d'actions américaines est l'ensemble des
    séances américaines ; elle ne se réduit que des trous réels.

    LE COMPROMIS PROFONDEUR/LARGEUR EST UN CHOIX, pas un accident. `fenetre_commune` fixe la
    profondeur par la COUVERTURE (garder 80 % des noms) : c'est ce qu'il faut pour mesurer un
    signal en coupe transversale, où la largeur fait l'information. Cette fonction-ci la fixe par
    le RANG (les 12 mieux couverts sur 30) : c'est ce qu'il faut pour une courbe affichée, où l'on
    préfère un historique long sur moins de titres — sinon elle démarrerait vers 2021 alors que la
    base remonte à 2015. Elle remplace `fenetre_par_rang`, devenu du code mort le 25/08.

    Ce que ça corrige : ces fonctions prenaient les dates d'UNE série de référence (la plus
    longue) et supposaient que les autres partageaient son calendrier. Avec des actions et des
    cryptos dans le même panier, cette supposition décalait les colonnes de plusieurs années.
    """
    import numpy as np

    par_sym: dict[str, dict[str, float]] = {}
    for s in syms:
        serie = {j: float(b.close) for b in (data.get(s) or [])
                 if (j := _jour(b)) and getattr(b, "close", None)}
        if serie:
            par_sym[s] = serie
    if not par_sym:
        return [], [], np.empty((0, 0))

    retenus = sorted(par_sym, key=lambda s: -len(par_sym[s]))[:max(1, min_noms)]
    dates_communes = set(par_sym[retenus[0]])
    for s in retenus[1:]:
        dates_communes &= set(par_sym[s])
    dates = sorted(dates_communes)
    if not dates:
        return [], [], np.empty((0, 0))
    A = np.asarray([[par_sym[s][j] for j in dates] for s in retenus], dtype=float)
    return retenus, dates, A


def rebalancements(L: int, start: int, step: int) -> int:
    """Nombre de pas qu'une fenêtre de longueur L autorise — à publier AVANT tout ratio.

    Un Sharpe annualisé sur moins de ~20 pas n'a pas d'intervalle de confiance utilisable ;
    l'afficher sans ce compte, c'est publier un chiffre qu'on ne peut pas contredire."""
    return max(0, len(range(start, max(start, L - 1), max(1, step))))
