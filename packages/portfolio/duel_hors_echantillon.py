"""Un écart moyen ne dit pas s'il est réel. Fenêtre par fenêtre, si.

POURQUOI CE MODULE. Le test hors échantillon met les segments bout à bout et publie UN
chiffre par allocateur. Le 09/09 sur l'univers assaini, cela donnait 1,04 % de CVaR pour
le Mean-CVaR plafonné contre 1,51 % pour HRP — et rien, dans cette forme, ne dit si
l'écart tient à une supériorité ou à une seule fenêtre chanceuse. Cinq segments
mis bout à bout ressemblent à une longue série ; ce sont cinq observations.

CE QU'ON MESURE ICI. Le détail par fenêtre, et un duel apparié : sur combien de fenêtres
l'un bat-il l'autre ? Un test des signes transforme ce décompte en probabilité — la
chance d'obtenir un tel score si les deux allocateurs se valaient.

DEUX LIMITES, DITES PLUTÔT QUE TUES.

  · LE PLANCHER DE PUISSANCE. Avec n fenêtres, la plus petite p-valeur atteignable est
    2/2ⁿ, même en gagnant TOUTES les fenêtres. À cinq fenêtres elle vaut 0,0625 : aucun
    résultat, si net soit-il, ne peut y descendre sous 5 %. Le savoir AVANT évite de
    lire un échec de puissance comme une absence d'effet.
  · LE RECOUVREMENT. Deux fenêtres consécutives partagent (fenêtre − pas)/fenêtre de
    leur période d'ajustement — 75 % à 252/63. Leurs poids se ressemblent, donc leurs
    résultats aussi, et le test des signes suppose l'indépendance. La p-valeur est donc
    OPTIMISTE : elle minore le hasard. On la publie avec ce défaut nommé.
"""

from __future__ import annotations

from math import comb

import numpy as np

__all__ = ["decoupes", "duel", "p_minimale", "performance_par_fenetre",
           "recouvrement_ajustement"]


def decoupes(n_dates: int, fenetre: int, pas: int) -> list[int]:
    """Indices de fin d'ajustement. Chaque segment hors échantillon est DISJOINT du
    suivant : seules les périodes d'ajustement se recouvrent."""
    if n_dates < fenetre + pas:
        return []
    return list(range(fenetre, n_dates - pas + 1, pas))


def p_minimale(n: int) -> float:
    """Plus petite p-valeur atteignable par un test des signes à n fenêtres.

    C'est le plancher de puissance : au-delà d'un score parfait il n'y a rien. Si cette
    valeur dépasse déjà le seuil qu'on vise, le protocole ne peut pas conclure et il
    faut plus de fenêtres, pas un meilleur allocateur."""
    return 1.0 if n <= 0 else min(1.0, 2.0 / (2 ** n))


def recouvrement_ajustement(fenetre: int, pas: int) -> float:
    """Part de la période d'ajustement partagée par deux fenêtres consécutives."""
    if fenetre <= 0:
        return 0.0
    return max(0.0, min(1.0, (fenetre - pas) / fenetre))


def performance_par_fenetre(rendements: np.ndarray, calculer, fenetre: int = 252,
                            pas: int = 63, alpha: float = 0.95) -> list[dict]:
    """Résultat hors échantillon de CHAQUE fenêtre, au lieu d'un agrégat.

    `calculer` reçoit la matrice d'ajustement et rend des poids. Une fenêtre où
    l'allocateur échoue est ABSENTE du résultat plutôt que remplacée par une valeur de
    convenance : un duel apparié doit comparer les mêmes fenêtres des deux côtés.
    """
    from packages.portfolio.cvar_optimize import cvar_du_portefeuille
    r = np.asarray(rendements, float)
    sortie = []
    for t in decoupes(r.shape[0], fenetre, pas):
        try:
            w = np.asarray(calculer(r[t - fenetre:t]), float)
        except Exception:  # noqa: BLE001 — l'échec d'un allocateur n'invalide pas les autres
            continue
        suite = r[t:t + pas] @ w
        sortie.append({
            "debut": int(t),
            "cvar": float(cvar_du_portefeuille(suite[:, None], [1.0], alpha)),
            "rendement": float(np.prod(1.0 + suite) - 1.0),
            "pire": float((-suite).max()) if suite.size else float("nan"),
        })
    return sortie


def _p_signes(gagnees: int, n: int) -> float:
    """Test des signes bilatéral : probabilité d'un score au moins aussi déséquilibré
    si les deux allocateurs se valaient (pile ou face à chaque fenêtre)."""
    if n <= 0:
        return 1.0
    extreme = max(gagnees, n - gagnees)
    queue = sum(comb(n, k) for k in range(extreme, n + 1))
    return min(1.0, 2.0 * queue / (2 ** n))


def duel(candidat: list[dict], reference: list[dict], champ: str = "cvar",
         plus_petit_est_mieux: bool = True) -> dict:
    """Duel apparié fenêtre à fenêtre entre deux allocateurs.

    Les fenêtres sont appariées par leur date de début : celles qu'un seul des deux a su
    traiter sont écartées des DEUX côtés. Comparer un allocateur sur ses bonnes fenêtres
    à un autre sur toutes les siennes donnerait un avantage qui ne vient que du tri.
    """
    par_debut = {d["debut"]: d for d in reference}
    paires = [(c[champ], par_debut[c["debut"]][champ]) for c in candidat
              if c["debut"] in par_debut]
    comparables = [(a, b) for a, b in paires if a != b]
    if plus_petit_est_mieux:
        gagnees = sum(1 for a, b in comparables if a < b)
    else:
        gagnees = sum(1 for a, b in comparables if a > b)
    n = len(comparables)
    return {
        "fenetres": len(paires),
        "comparables": n,
        "gagnees": gagnees,
        "p": _p_signes(gagnees, n),
        "p_minimale": p_minimale(n),
        "concluant": n > 0 and _p_signes(gagnees, n) <= 0.05,
        "ecart_median": (float(np.median([a - b for a, b in paires]))
                         if paires else float("nan")),
    }
