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


def rebalancements(L: int, start: int, step: int) -> int:
    """Nombre de pas qu'une fenêtre de longueur L autorise — à publier AVANT tout ratio.

    Un Sharpe annualisé sur moins de ~20 pas n'a pas d'intervalle de confiance utilisable ;
    l'afficher sans ce compte, c'est publier un chiffre qu'on ne peut pas contredire."""
    return max(0, len(range(start, max(start, L - 1), max(1, step))))
