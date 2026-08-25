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


def fenetre_par_rang(data: dict, syms: list[str], min_noms: int) -> tuple[list[str], int]:
    """Variante par RANG : garder les `min_noms` séries aux plus longs historiques.

    Pourquoi deux règles coexistent — et ce n'est pas un oubli. `fenetre_commune` fixe la
    profondeur par la COUVERTURE (garder 80 % des noms) : c'est ce qu'il faut pour mesurer un
    signal en coupe transversale, où la largeur fait l'information. Cette variante-ci fixe la
    profondeur par le RANG (garder les 12 plus anciens sur 30) : c'est ce qu'il faut pour la
    courbe d'equity du tableau de bord et le journal de trades, où l'on préfère un historique
    long sur moins de titres à un historique court sur tous — sinon la courbe affichée
    démarrait vers 2021 alors que la base remonte à 2015.

    Le compromis profondeur/largeur est donc un CHOIX explicite selon l'usage, pas un accident.
    Ce bloc vivait en trois copies identiques dans `preset_backtest` ; la sémantique est
    inchangée, seul l'endroit où elle est écrite a changé.
    """
    longueurs = sorted((len(data[s]) for s in syms), reverse=True)
    if not longueurs:
        return list(syms), 0
    requis = longueurs[min(max(1, min_noms), len(longueurs)) - 1]
    retenus = [s for s in syms if len(data[s]) >= requis] or list(syms)
    return retenus, min(len(data[s]) for s in retenus)


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


def rebalancements(L: int, start: int, step: int) -> int:
    """Nombre de pas qu'une fenêtre de longueur L autorise — à publier AVANT tout ratio.

    Un Sharpe annualisé sur moins de ~20 pas n'a pas d'intervalle de confiance utilisable ;
    l'afficher sans ce compte, c'est publier un chiffre qu'on ne peut pas contredire."""
    return max(0, len(range(start, max(start, L - 1), max(1, step))))
