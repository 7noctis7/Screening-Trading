"""Pourquoi le modèle a-t-il dit ça — mesuré, pas raconté.

Le site sait déjà expliquer une DÉCISION : `/fiche` détaille ses six étages et compte
ceux qui sont réellement mesurés. Mais le score du modèle d'apprentissage y entre comme
un nombre opaque. « Le modèle donne 68 % » n'est pas une explication : c'est la chose
même qu'il faudrait expliquer.

C'est le manque que comble `cuml.explainer` (SHAP) dans l'écosystème NVIDIA. La méthode
est indépendante du matériel : le GPU la rend plus rapide, il ne la rend pas possible.
Elle est donc implémentée ici en numpy, sans dépendance nouvelle.

DEUX LECTURES, QUI NE RÉPONDENT PAS À LA MÊME QUESTION

1. `importance_par_permutation` — « sur QUOI ce modèle s'appuie-t-il, en général ? »
   On mélange une colonne au hasard et on regarde de combien la performance tombe. Si
   rien ne tombe, le modèle ne s'en servait pas. C'est une mesure GLOBALE.

2. `valeurs_de_shapley` — « pourquoi CE titre-là, aujourd'hui ? »
   Chaque variable reçoit sa part du écart entre la prédiction et la prédiction moyenne.
   C'est une mesure LOCALE, la seule qui réponde à « pourquoi lui et pas un autre ».

LA PROPRIÉTÉ QUI REND CE CALCUL VÉRIFIABLE
Les valeurs de Shapley somment exactement à `f(x) − moyenne(f(fond))` : c'est
l'efficience, un théorème, pas une approximation heureuse. Elle est testée. Une
implémentation qui la viole est fausse — et c'est le seul garde-fou qui distingue un
vrai calcul d'attribution d'un histogramme joliment normalisé.

CE QUE ÇA NE DIT PAS
Une attribution n'est pas une cause. Elle dit de quoi le MODÈLE s'est servi, pas ce qui
fait monter un cours. Un modèle qui s'appuierait sur une variable absurde recevrait ici
une explication parfaitement lisible de son absurdité — ce qui est justement l'intérêt.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

__all__ = ["contributions_lisibles", "fond_effectif", "importance_par_permutation",
           "valeurs_de_shapley"]


def importance_par_permutation(predire: Callable[[np.ndarray], np.ndarray],
                               X: np.ndarray, y: np.ndarray,
                               noms: Sequence[str] | None = None,
                               n_repetitions: int = 10,
                               graine: int = 0) -> list[dict]:
    """De combien la performance tombe quand on détruit une variable.

    On mélange UNE colonne — le modèle n'est pas ré-entraîné, seule l'information de
    cette variable disparaît. Répété plusieurs fois : un seul mélange peut, par chance,
    tomber sur une permutation peu destructrice.

    Une importance NÉGATIVE n'est pas une anomalie : elle signifie que détruire la
    variable a amélioré le score, donc qu'elle apportait du bruit. La rendre à zéro
    masquerait précisément le cas intéressant.
    """
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    if X.ndim != 2 or X.shape[0] != y.size:
        raise ValueError("X doit être (n × d) et y de longueur n")
    noms = list(noms) if noms is not None else [f"v{i}" for i in range(X.shape[1])]
    if len(noms) != X.shape[1]:
        raise ValueError("un nom par colonne")

    base = _score(predire(X), y)
    rng = np.random.default_rng(graine)
    out = []
    for j in range(X.shape[1]):
        chutes = []
        for _ in range(n_repetitions):
            melange = X.copy()
            melange[:, j] = rng.permutation(melange[:, j])
            chutes.append(base - _score(predire(melange), y))
        arr = np.asarray(chutes, float)
        out.append({"variable": noms[j], "importance": float(arr.mean()),
                    "ecart_type": float(arr.std(ddof=1)) if arr.size > 1 else 0.0})
    out.sort(key=lambda d: d["importance"], reverse=True)
    return out


def _score(proba: np.ndarray, y: np.ndarray) -> float:
    """Exactitude d'un classement binaire. Séparé pour rester testable seul."""
    p = np.asarray(proba, float).ravel()
    return float(((p >= 0.5).astype(float) == y).mean())


def fond_effectif(fond: np.ndarray, max_references: int = 100) -> np.ndarray:
    """Le fond réellement utilisé : sous-échantillon RÉGULIER si le fond est trop gros.

    Régulier et non aléatoire, pour deux raisons. Le coût du calcul est proportionnel à
    la taille du fond, donc il faut le borner. Et surtout : l'efficience de Shapley est
    exacte par rapport au fond EFFECTIVEMENT parcouru — un tirage aléatoire la rendrait
    approximative, et une propriété approximative ne peut plus servir de garde-fou.
    """
    fond = np.asarray(fond, float)
    if fond.ndim != 2:
        raise ValueError("le fond doit être une matrice (m références × d variables)")
    if fond.shape[0] <= max_references:
        return fond
    pas = np.linspace(0, fond.shape[0] - 1, max_references).astype(int)
    return fond[pas]


def valeurs_de_shapley(predire: Callable[[np.ndarray], np.ndarray],
                       x: np.ndarray, fond: np.ndarray,
                       permutations_par_reference: int = 4,
                       max_references: int = 100, graine: int = 0) -> np.ndarray:
    """Part de chaque variable dans l'écart entre `f(x)` et la prédiction moyenne.

    On part d'un individu de RÉFÉRENCE tiré des données réelles — jamais d'un vecteur de
    zéros, qui n'existe nulle part et donnerait une explication par rapport à un titre
    imaginaire — puis on remplace les variables une à une dans l'ordre d'une permutation
    tirée au sort, en notant de combien la prédiction bouge à chaque remplacement.

    CHAQUE référence est parcourue le MÊME nombre de fois. Une première version en
    tirait une au hasard à chaque permutation : la somme des contributions retombait
    alors sur la moyenne de l'échantillon TIRÉ, pas sur celle du fond, et l'efficience
    — la seule propriété qui permette de vérifier le calcul — n'était plus exacte. Le
    parcours systématique la rétablit sans rien coûter de plus.

    Déterministe à graine fixée : deux explications du même titre au même instant
    doivent coïncider, sans quoi ce ne sont pas des explications.
    """
    x = np.asarray(x, float).ravel()
    ref = fond_effectif(fond, max_references)
    if ref.shape[1] != x.size:
        raise ValueError("le fond doit avoir autant de colonnes que x")
    if permutations_par_reference < 1:
        raise ValueError("il faut au moins une permutation par référence")
    d = x.size
    rng = np.random.default_rng(graine)
    phi = np.zeros(d)

    for z in ref:
        for _ in range(permutations_par_reference):
            ordre = rng.permutation(d)
            # Les d+1 états intermédiaires sont prédits EN UN SEUL appel : d appels
            # séparés par permutation rendraient la méthode inutilisable sur un modèle
            # lent, ce qui est la raison habituelle de ne pas expliquer ses modèles.
            etats = np.repeat(z[None, :], d + 1, axis=0)
            for k, j in enumerate(ordre):
                etats[k + 1:, j] = x[j]
            phi[ordre] += np.diff(np.asarray(predire(etats), float).ravel())
    return phi / (ref.shape[0] * permutations_par_reference)


def contributions_lisibles(phi: np.ndarray, noms: Sequence[str],
                           garder: int = 6) -> list[dict]:
    """Les contributions triées par ampleur, prêtes à afficher.

    On garde les plus fortes en valeur ABSOLUE : une variable qui pousse fortement à la
    baisse explique autant qu'une qui pousse à la hausse. Trier sur la valeur signée
    ferait disparaître les raisons de se méfier.
    """
    phi = np.asarray(phi, float).ravel()
    noms = list(noms)
    if phi.size != len(noms):
        raise ValueError("un nom par contribution")
    paires = sorted(zip(noms, phi, strict=True), key=lambda t: abs(t[1]), reverse=True)
    return [{"variable": n, "contribution": float(v),
             "sens": "pousse à la hausse" if v > 0 else
                     "pousse à la baisse" if v < 0 else "sans effet"}
            for n, v in paires[:garder]]
