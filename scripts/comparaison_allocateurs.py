"""L'étape 3 de la validation : comparer les allocateurs, et dire ce que ça vaut.

Sorti de `scripts/valider_nouveautes.py`, qui dépassait largement les 400 lignes que
s'impose le projet. Le découpage suit une frontière réelle : ici on compare des
allocateurs et on IMPRIME un verdict ; là-bas on orchestre les quatre étapes.

Le cœur du raisonnement statistique vit un cran plus bas encore, dans
`packages/portfolio/duel_hors_echantillon.py` : ce module-ci ne fait que le mettre en
forme, avec ses deux honnêtetés obligatoires — le plancher de puissance et le
recouvrement des fenêtres d'ajustement.
"""

from __future__ import annotations

import numpy as np

# Plafond par ligne de la variante contrainte. Une allocation qui met la moitié du
# capital sur un actif réduit peut-être la perte extrême MESURÉE, mais elle expose à ce
# que la mesure n'a pas vu.
#
# DÉFINI ICI ET NULLE PART AILLEURS. Le tableau EN échantillon et le tableau HORS
# échantillon doivent plafonner au même niveau : deux constantes jumelles qui divergent
# feraient comparer deux allocateurs différents sous le même nom, sans que rien ne le
# signale — le genre d'écart qu'on ne retrouve qu'en relisant les deux fichiers.
PLAFOND_LIGNE = 0.25


def _allocateurs(r: np.ndarray) -> list[tuple[str, callable]]:
    """Les allocateurs comparés, sous forme de FONCTIONS d'un historique.

    Sous forme de fonctions et non de poids figés : le test hors échantillon doit
    pouvoir les réajuster sur chaque fenêtre passée, ce qu'une liste de poids calculée
    une fois pour toutes interdit.
    """
    from packages.portfolio.cvar_optimize import mean_cvar_weights
    from packages.portfolio.optimize import (
        equal_risk_contribution,
        hrp_weights,
        min_variance_weights,
    )
    return [
        ("Mean-CVaR (nouveau)", lambda h: mean_cvar_weights(h, alpha=0.95)),
        (f"Mean-CVaR plafonné {PLAFOND_LIGNE:.0%}",
         lambda h: mean_cvar_weights(h, alpha=0.95, plafond=PLAFOND_LIGNE)),
        ("min-variance", lambda h: min_variance_weights(np.cov(h, rowvar=False))),
        ("risk parity (ERC)",
         lambda h: equal_risk_contribution(np.cov(h, rowvar=False))),
        ("HRP", lambda h: hrp_weights(np.cov(h, rowvar=False))),
        ("équipondéré", lambda h: [1.0 / h.shape[1]] * h.shape[1]),
    ]


REFERENCE = "HRP"          # l'allocateur en place : c'est lui qu'il faut battre


def _p_texte(p: float) -> str:
    """Une p-valeur non nulle ne doit pas s'afficher « 0.000 ».

    Le plancher de puissance à seize fenêtres vaut 3,05·10⁻⁵ : arrondi à trois
    décimales, il s'imprimait « 0.0000 » — un zéro qui n'existe pas, dans un projet
    dont toute la discipline est de ne jamais publier un chiffre qu'on n'a pas."""
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"


def _colonne_duel(d: dict) -> str:
    """Score, p-valeur et SENS du résultat.

    La première version marquait « ✓ » dès que le test des signes concluait — donc
    aussi pour l'équipondéré, battu 0 fois sur 16. Une coche à côté d'un perdant se lit
    comme une validation. Le test des signes est bilatéral : il dit qu'il y a un écart,
    jamais dans quel sens. Le sens, c'est le décompte qui le donne."""
    n = d["comparables"]
    if not n:
        return f"{'—':>26s}"
    gagnant = d["gagnees"] * 2 > n
    sens = ("mieux" if gagnant else "pire") if d["concluant"] else "—"
    return f"{d['gagnees']:>3d}/{n:<3d} {_p_texte(d['p']):>8s} {sens:>7s}"


def _duels(detail: dict, fenetre: int, pas: int) -> None:
    """Le duel apparié, fenêtre à fenêtre, contre l'allocateur en place.

    Un écart de moyennes ne dit pas s'il est réel : cinq segments mis bout à bout
    ressemblent à une longue série, ce sont cinq observations. On compte donc sur
    combien de fenêtres chaque candidat bat HRP, et ce que vaut ce score au hasard.
    """
    from packages.portfolio.duel_hors_echantillon import (
        duel,
        p_minimale,
        recouvrement_ajustement,
    )
    ref = detail.get(REFERENCE) or []
    if not ref:
        return
    plancher = p_minimale(len(ref))
    print(f"\n  DUEL APPARIÉ contre {REFERENCE}, fenêtre par fenêtre")
    print(f"  {'allocation':24s} {'CVaR (moins = mieux)':>26s}   "
          f"{'rendement (plus = mieux)':>26s}")
    for nom, perf in detail.items():
        if nom == REFERENCE or not perf:
            continue
        risque = duel(perf, ref, "cvar", plus_petit_est_mieux=True)
        gain = duel(perf, ref, "rendement", plus_petit_est_mieux=False)
        print(f"  {nom:24s} {_colonne_duel(risque)}   {_colonne_duel(gain)}")
    print("\n  « mieux »/« pire » disent le SENS, la p-valeur seulement si l'écart")
    print("  est trop net pour un tirage à pile ou face. Un allocateur battu de façon")
    print("  concluante est marqué « pire » : c'est un résultat, pas une validation.")
    print(f"\n  PLANCHER DE PUISSANCE : avec {len(ref)} fenêtres, la plus petite "
          f"p-valeur atteignable est {_p_texte(plancher)}")
    if plancher > 0.05:
        print("  — donc AUCUN résultat, si net soit-il, ne peut conclure à 5 % ici.")
        print(f"  Il faut plus de fenêtres : relancer avec --pas {max(5, pas // 3)}.")
    part = recouvrement_ajustement(fenetre, pas)
    print(f"  Deux fenêtres consécutives partagent {part:.0%} de leur période "
          "d'ajustement :")
    print("  leurs poids se ressemblent, donc leurs résultats aussi. La p-valeur")
    print("  ci-dessus est OPTIMISTE — elle minore le hasard.")


def _hors_echantillon(r: np.ndarray, fenetre: int = 252, pas: int = 63,
                      dates: list | None = None) -> None:
    """LE test qui décide. Ajuster sur le passé, mesurer sur la SUITE.

    Tout ce qui précède est mesuré EN ÉCHANTILLON : chaque allocateur est ajusté sur les
    mêmes jours que ceux qui servent à le noter. Mean-CVaR minimise exactement le nombre
    qu'on rapporte — il ne PEUT PAS perdre ce concours, c'est sa fonction objectif. Et
    min-variance perd sur le CVaR par construction, pas par infériorité. « 0,58 % contre
    1,65 % » ne prouve donc rien d'autre que « l'optimiseur a bien optimisé ce qu'on lui
    a demandé ».

    Ici, les poids sont calculés sur une fenêtre passée puis appliqués à la fenêtre
    SUIVANTE, jamais vue. Les segments hors échantillon sont mis bout à bout et notés
    ensemble. Un avantage qui survit à ça est réel ; un avantage qui s'évapore était du
    surajustement — et les deux se ressemblent parfaitement en échantillon.

    Le RENDEMENT est publié à côté du risque. Un allocateur qui divise la perte extrême
    par trois en divisant aussi le rendement par trois n'a rien amélioré : il a
    simplement moins investi.
    """
    from packages.portfolio.cvar_optimize import cvar_du_portefeuille
    if r.shape[0] < fenetre + pas:
        print(f"\n  (hors échantillon impossible : {r.shape[0]} dates, il en faut "
              f"{fenetre + pas} au minimum)")
        return
    from packages.portfolio.duel_hors_echantillon import (
        decoupes,
        performance_par_fenetre,
    )
    coupes = decoupes(r.shape[0], fenetre, pas)
    n_fenetres = len(coupes)
    print(f"\n  HORS ÉCHANTILLON — ajusté sur {fenetre} jours, mesuré sur les {pas}")
    print(f"  suivants, {n_fenetres} fois de suite. C'est le seul test qui décide.")
    if dates and coupes and len(dates) == r.shape[0]:
        fin = min(coupes[-1] + pas, len(dates)) - 1
        print(f"  Période RÉELLEMENT mesurée : {str(dates[coupes[0]])[:10]} → "
              f"{str(dates[fin])[:10]} ({coupes[-1] + pas - coupes[0]} séances).")
        print("  Un allocateur ne se juge pas hors de son régime : une poche")
        print("  obligataire brille sur certaines années et s'effondre sur d'autres.")
    print(f"\n  {'allocation':24s} {'CVaR 95%':>10s} {'pire jour':>10s} "
          f"{'rendement':>11s}")
    detail = {}
    for nom, calculer in _allocateurs(r):
        detail[nom] = performance_par_fenetre(r, calculer, fenetre, pas)
        morceaux = []
        for t in decoupes(r.shape[0], fenetre, pas):
            try:
                w = np.asarray(calculer(r[t - fenetre:t]), float)
            except Exception:  # noqa: BLE001 — un allocateur en échec ne fausse pas
                continue        # les autres ; il sera simplement absent du décompte
            morceaux.append(r[t:t + pas] @ w)
        if not morceaux:
            print(f"  {nom:24s} {'—':>10s} {'—':>10s} {'—':>11s}")
            continue
        suite = np.concatenate(morceaux)
        cumul = float(np.prod(1.0 + suite) - 1.0)
        print(f"  {nom:24s} "
              f"{cvar_du_portefeuille(suite[:, None], [1.0]):>9.2%} "
              f"{(-suite).max():>9.2%} {cumul:>10.1%}")
    _duels(detail, fenetre, pas)
    print("\n  À LIRE : si l'avantage du Mean-CVaR disparaît ici, il était du")
    print("  surajustement. S'il tient, il est réel — et le rendement dit son coût.")


