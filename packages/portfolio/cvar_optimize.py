"""Optimisation Mean-CVaR — minimiser la PERTE EXTRÊME, pas la dispersion.

POURQUOI CE FICHIER EXISTE

Tous les optimiseurs de `optimize.py` raisonnent en variance : variance minimale, poids
inverses à la variance, égalisation des contributions au risque. La variance traite une
journée à +8 % et une journée à −8 % exactement pareil. Ce n'est pas une approximation
gênante, c'est la mauvaise question : personne ne se ruine sur des hausses.

Mesuré dans ce projet le 06/09 : sur neuf actifs à ~73 % de volatilité et un à 18 %,
min-variance pose 87 % sur le plus calme (99 % sur certains profils). Ce n'est pas un
défaut d'implémentation — minimiser la variance CONCENTRE sur l'actif de plus faible
variance, c'est sa définition. Mais « le plus calme » et « celui qui perdra le moins le
jour où tout tombe » sont deux actifs différents dès que les pertes ne sont pas
symétriques : un actif qui dérive doucement puis s'effondre a une variance modeste et
une
queue catastrophique.

Le CVaR répond à la seconde question. `risk_metrics.cvar_historical` savait déjà le
CALCULER — pour le rapport, jamais pour décider. Ici il devient l'objectif.

CE QUE ÇA NE RÉPARE PAS, ET IL FAUT LE DIRE
Une série ARRÊTÉE (cours figé) paraît sans risque à la variance ET au CVaR : sans
mouvement, il n'y a ni dispersion ni queue. C'est le contrôle de fraîcheur
(`user_analysis.diagnostic_par_actif`) qui protège de ça, pas cet optimiseur.

MÉTHODE — Rockafellar & Uryasev (2000)
Pour un seuil `z`, la quantité `z + moyenne_des_dépassements/(1−α)` majore le CVaR, et
son minimum en `z` VAUT le CVaR. On minimise donc conjointement sur `z` et sur les
poids.
Astuce qui rend le tout stable : à poids fixés, le `z` optimal a une forme fermée —
c'est
le quantile α des pertes (la VaR). On alterne donc quantile exact puis pas de gradient
projeté sur les poids ; aucun solveur externe, numpy seul, comme le reste du module.

Le blueprint NVIDIA `portfolio-optimization` résout ce même programme par un solveur LP
sur GPU (cuOpt) et annonce jusqu'à 160× — sur H100, et sur le SOLVEUR. La formulation
ci-
dessous est la même ; seule la façon de la résoudre changerait. C'est voulu : l'idée est
portable aujourd'hui, l'accélération viendra si la mesure la justifie.
"""

from __future__ import annotations

import numpy as np

__all__ = ["cvar_du_portefeuille", "mean_cvar_detail", "mean_cvar_weights",
           "projeter_simplexe"]


def projeter_simplexe(v: np.ndarray, plafond: float | None = None) -> np.ndarray:
    """Projette `v` sur {w ≥ 0, Σw = 1, w ≤ plafond} — le plus proche point admissible.

    Sans plafond c'est la projection classique sur le simplexe. Avec plafond, on cherche
    le seuil θ tel que Σ borne(vᵢ − θ) = 1 : la somme décroît continûment avec θ, une
    bisection la trouve sans risque de division par zéro ni de cas particulier.
    """
    v = np.asarray(v, float).ravel()
    n = v.size
    if n == 0:
        return v
    haut = float(plafond) if plafond else 1.0
    if haut * n < 1.0 - 1e-12:
        # Plafond trop bas pour totaliser 100 % : on rend l'équipondéré plutôt qu'un
        # portefeuille qui n'investirait pas tout sans le dire.
        return np.full(n, 1.0 / n)

    def somme(theta: float) -> float:
        return float(np.clip(v - theta, 0.0, haut).sum())

    lo, hi = float(v.min() - haut - 1.0), float(v.max())
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if somme(mid) > 1.0:
            lo = mid
        else:
            hi = mid
    w = np.clip(v - 0.5 * (lo + hi), 0.0, haut)
    total = w.sum()
    return w / total if total > 0 else np.full(n, 1.0 / n)


def cvar_du_portefeuille(scenarios, poids, alpha: float = 0.95) -> float:
    """Perte moyenne dans les (1−α) pires scénarios. Positif = perte.

    `scenarios` : matrice (T scénarios × N actifs) de RENDEMENTS. C'est la même
convention que partout ailleurs dans le module — une matrice de pertes passée ici
    par
    erreur donnerait un CVaR négatif, ce qui se voit immédiatement.
    """
    r = np.asarray(scenarios, float)
    w = np.asarray(poids, float).ravel()
    if r.ndim != 2 or r.shape[1] != w.size or r.shape[0] == 0:
        raise ValueError("scenarios doit être (T × N) et poids de taille N")
    pertes = -(r @ w)
    k = max(1, int(round((1.0 - alpha) * pertes.size)))
    pires = np.sort(pertes)[-k:]
    return float(pires.mean())


def _quantile_pertes(pertes: np.ndarray, alpha: float) -> float:
    """Le `z` optimal de Rockafellar-Uryasev : la VaR, quantile α des pertes."""
    return float(np.quantile(pertes, alpha))


def _gradient(r: np.ndarray, w: np.ndarray, z: float, alpha: float,
              aversion: float, moyenne: np.ndarray) -> np.ndarray:
    """Sous-gradient de l'objectif par rapport aux poids.

    Seuls les scénarios de la QUEUE (perte au-delà de la VaR) contribuent : c'est
    exactement ce qu'on veut, l'optimiseur ne regarde que les mauvais jours.
    """
    pertes = -(r @ w)
    queue = pertes > z
    if not queue.any():
        return -aversion * moyenne
    denom = (1.0 - alpha) * r.shape[0]
    return -(r[queue].sum(axis=0)) / denom - aversion * moyenne


def _resoudre_lp(r: np.ndarray, alpha: float, aversion: float,
                 plafond: float | None) -> np.ndarray | None:
    """Optimum EXACT par programmation linéaire. `None` si scipy est absent.

    Rockafellar-Uryasev se met sous forme linéaire en introduisant une variable de
    dépassement `u_t` par scénario :

        minimiser   z + Σ u_t / ((1−α)·T)  −  aversion · (moyenne · w)
        sous        u_t ≥ −(r_t · w) − z,   u_t ≥ 0,   Σw = 1,   0 ≤ w ≤ plafond

    C'est la formulation que le blueprint NVIDIA `portfolio-optimization` confie à
    cuOpt sur GPU. Ici HiGHS la résout sur processeur : même programme, même optimum,
    seul le temps de résolution change. La matrice de contraintes est CREUSE — dense,
    dix ans de scénarios sur cent actifs demanderaient plusieurs gigaoctets pour rien.
    """
    try:
        from scipy.optimize import linprog
        from scipy.sparse import csr_matrix, eye, hstack
    except Exception:  # noqa: BLE001 — scipy optionnel : le repli prend la main
        return None
    t, n = r.shape
    poids_queue = 1.0 / ((1.0 - alpha) * t)
    cout = np.concatenate([-aversion * r.mean(axis=0), [1.0],
                           np.full(t, poids_queue)])
    a_ub = hstack([csr_matrix(-r), csr_matrix(-np.ones((t, 1))), -eye(t, format="csr")],
                  format="csr")
    a_eq = csr_matrix(np.concatenate([np.ones(n), np.zeros(1 + t)])[None, :])
    bornes = [(0.0, float(plafond) if plafond else 1.0)] * n + [(None, None)] \
        + [(0.0, None)] * t
    res = linprog(cout, A_ub=a_ub, b_ub=np.zeros(t), A_eq=a_eq, b_eq=[1.0],
                  bounds=bornes, method="highs")
    if not res.success:
        return None
    w = np.clip(np.asarray(res.x[:n], float), 0.0, None)
    total = w.sum()
    return w / total if total > 0 else None


def _resoudre_sousgradient(r: np.ndarray, alpha: float, aversion: float,
                           plafond: float | None, iters: int) -> np.ndarray:
    """Repli sans scipy : sous-gradient projeté, `z` remis à sa valeur exacte à chaque
    tour (le quantile des pertes).

    Le pas est calé sur le DIAMÈTRE du domaine (√2 pour le simplexe), pas sur
    l'amplitude des rendements. La première version faisait l'inverse et n'avançait
    quasiment pas : partie de 50 %, elle finissait à 44 % là où l'optimum était à 15 %,
    donc pire que min-variance sur son propre objectif. Une erreur de mise à l'échelle
    ne se voit pas — le code tourne, converge en apparence, et rend une mauvaise
    réponse. C'est le test de comparaison qui l'a attrapée, pas la lecture.
    """
    n = r.shape[1]
    moyenne = r.mean(axis=0)
    w = projeter_simplexe(np.full(n, 1.0 / n), plafond)
    meilleur_w, meilleur_score = w.copy(), np.inf
    diametre = np.sqrt(2.0)
    for k in range(iters):
        z = _quantile_pertes(-(r @ w), alpha)
        score = cvar_du_portefeuille(r, w, alpha) - aversion * float(moyenne @ w)
        if score < meilleur_score:
            meilleur_score, meilleur_w = score, w.copy()
        g = _gradient(r, w, z, alpha, aversion, moyenne)
        norme = float(np.linalg.norm(g)) or 1.0
        w = projeter_simplexe(w - (diametre / (norme * np.sqrt(k + 1.0))) * g, plafond)
    # On rend le MEILLEUR point visité, pas le dernier : un sous-gradient ne décroît
    # pas de façon monotone, et le dernier pas peut être moins bon que celui d'avant.
    return meilleur_w


def _valider(scenarios) -> np.ndarray:
    r = np.asarray(scenarios, float)
    if r.ndim != 2 or r.shape[0] < 2 or r.shape[1] < 1:
        raise ValueError("scenarios doit être une matrice (T ≥ 2) × (N ≥ 1)")
    return np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0)


def mean_cvar_detail(scenarios, alpha: float = 0.95, aversion: float = 0.0,
                     plafond: float | None = None, iters: int = 800) -> dict:
    """Poids Mean-CVaR + la MÉTHODE employée + le CVaR obtenu.

    La méthode est publiée parce qu'elle change la nature du résultat : « exact » est
    l'optimum du programme, « approché » en est une estimation. Confondre les deux
    ferait comparer des chiffres qui ne sont pas de même nature.
    """
    r = _valider(scenarios)
    if r.shape[1] == 1:
        return {"poids": [1.0], "methode": "trivial",
                "cvar": cvar_du_portefeuille(r, [1.0], alpha)}
    w = _resoudre_lp(r, alpha, aversion, plafond)
    methode = "exact (programmation linéaire)"
    if w is None:
        w = _resoudre_sousgradient(r, alpha, aversion, plafond, iters)
        methode = "approché (sous-gradient projeté, scipy absent)"
    return {"poids": [float(x) for x in w], "methode": methode,
            "cvar": cvar_du_portefeuille(r, w, alpha)}


def mean_cvar_weights(scenarios, alpha: float = 0.95, aversion: float = 0.0,
                      plafond: float | None = None, iters: int = 800) -> list[float]:
    """Poids long-only minimisant le CVaR (moins `aversion` × rendement espéré).

    `aversion = 0` → CVaR pur : on ne cherche QUE la protection à la baisse. Au-dessus,
    on accepte un peu de queue en échange de rendement espéré ; c'est le curseur qui
    engendre la frontière efficiente en Mean-CVaR.

    Déterministe : aucun tirage aléatoire, ni dans le solveur exact ni dans le repli.
    Deux appels sur les mêmes scénarios rendent le même vecteur — sans quoi comparer
    deux versions du code serait impossible (leçon du 07/09 sur un banc instable).
    """
    return mean_cvar_detail(scenarios, alpha, aversion, plafond, iters)["poids"]
