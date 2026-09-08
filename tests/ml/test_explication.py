"""Une attribution qui ne somme pas juste n'est pas une attribution.

Le score du modèle entrait dans le site comme un nombre opaque : « le modèle donne
68 % » n'explique rien, c'est la chose même qu'il faudrait expliquer. Ce module comble
ce manque — le même que comble `cuml.explainer` côté NVIDIA, par une méthode
indépendante du matériel.

LE GARDE-FOU CENTRAL EST L'EFFICIENCE. Les valeurs de Shapley somment EXACTEMENT à
`f(x) − moyenne(f(fond))`. C'est un théorème, pas une approximation heureuse : une
implémentation qui le viole est fausse. Sans ce test, n'importe quel histogramme
normalisé passerait pour une explication.

Modèles jouets à réponse CONNUE : on vérifie que la méthode retrouve ce qu'on a mis
dedans. Sur un vrai modèle, on ne saurait pas distinguer une bonne attribution d'une
mauvaise — c'est exactement pour ça qu'on ne teste pas là-dessus.
"""

from __future__ import annotations

import numpy as np
import pytest

from packages.ml.explication import (
    contributions_lisibles,
    fond_effectif,
    importance_par_permutation,
    valeurs_de_shapley,
)

# --------------------------------------------------------------- Shapley

def test_l_efficience_est_respectee() -> None:
    """Somme des contributions = f(x) − moyenne(f(fond)). Le théorème, vérifié."""
    def predire(X):
        X = np.atleast_2d(X)
        return 0.3 * X[:, 0] - 0.7 * X[:, 1] + 0.1 * X[:, 2]

    rng = np.random.default_rng(1)
    fond = rng.normal(size=(200, 3))
    x = np.array([1.5, -2.0, 0.5])
    phi = valeurs_de_shapley(predire, x, fond, permutations_par_reference=3, graine=0)
    ref = fond_effectif(fond)
    attendu = float(predire(x[None, :])[0] - predire(ref).mean())
    assert phi.sum() == pytest.approx(attendu, abs=1e-9), (
        f"somme {phi.sum():.6f} contre {attendu:.6f} : l'attribution ne conserve pas "
        "l'écart qu'elle prétend répartir — elle est fausse."
    )


def test_une_variable_ignoree_recoit_zero() -> None:
    """Un modèle qui n'utilise pas une variable ne doit pas lui devoir d'explication."""
    def predire(X):
        X = np.atleast_2d(X)
        return X[:, 0] * 2.0            # la colonne 1 n'entre jamais dans le calcul

    rng = np.random.default_rng(2)
    fond = rng.normal(size=(150, 2))
    phi = valeurs_de_shapley(predire, np.array([1.0, 9.9]), fond, 3, graine=0)
    assert abs(phi[1]) < 1e-9, f"variable inutilisée créditée de {phi[1]:.4f}"
    assert abs(phi[0]) > 0.1, "la variable réellement utilisée n'est pas créditée"


def test_le_signe_suit_le_sens_de_l_effet() -> None:
    """Une variable qui pousse à la baisse doit recevoir une contribution NÉGATIVE.
    Un signe inversé rendrait chaque explication trompeuse tout en restant lisible."""
    def predire(X):
        X = np.atleast_2d(X)
        return -3.0 * X[:, 0]

    fond = np.zeros((50, 1))
    phi = valeurs_de_shapley(predire, np.array([2.0]), fond, 2, graine=0)
    assert phi[0] < 0


def test_l_explication_est_deterministe() -> None:
    """Deux explications du même titre au même instant doivent coïncider — sinon ce ne
    sont pas des explications."""
    def predire(X):
        return np.atleast_2d(X).sum(axis=1)

    fond = np.random.default_rng(3).normal(size=(80, 4))
    x = np.array([1.0, 2.0, 3.0, 4.0])
    a = valeurs_de_shapley(predire, x, fond, 3, graine=5)
    b = valeurs_de_shapley(predire, x, fond, 3, graine=5)
    assert np.array_equal(a, b)


def test_un_fond_mal_dimensionne_leve() -> None:
    with pytest.raises(ValueError):
        valeurs_de_shapley(lambda X: np.zeros(len(X)), np.zeros(3), np.zeros((10, 5)))


# ------------------------------------------------- importance par permutation

def test_la_variable_qui_porte_le_signal_ressort_en_tete() -> None:
    """Colonne 0 = le label bruité, les autres = du bruit pur."""
    rng = np.random.default_rng(4)
    y = (rng.random(400) > 0.5).astype(float)
    X = np.column_stack([y + rng.normal(0, 0.15, 400), rng.normal(size=(400, 3))])

    def predire(M):
        return np.atleast_2d(M)[:, 0]        # le modèle ne lit QUE la colonne 0

    imp = importance_par_permutation(predire, X, y, ["signal", "b1", "b2", "b3"],
                                     n_repetitions=6, graine=0)
    assert imp[0]["variable"] == "signal", f"classement inattendu : {imp}"
    assert imp[0]["importance"] > 0.2, "détruire le signal ne coûte presque rien"


def test_du_bruit_pur_ne_recoit_pas_d_importance() -> None:
    """Contrôle négatif : sans lien, mélanger une colonne ne doit rien changer."""
    rng = np.random.default_rng(5)
    X = rng.normal(size=(300, 3))
    y = (rng.random(300) > 0.5).astype(float)

    def predire(M):
        return np.atleast_2d(M)[:, 0]

    imp = importance_par_permutation(predire, X, y, ["a", "b", "c"],
                                     n_repetitions=8, graine=0)
    assert max(abs(d["importance"]) for d in imp) < 0.12, (
        f"des variables sans lien reçoivent de l'importance : {imp}"
    )


def test_un_nom_par_colonne_est_exige() -> None:
    with pytest.raises(ValueError):
        importance_par_permutation(lambda M: np.zeros(len(M)), np.zeros((10, 3)),
                                   np.zeros(10), ["a", "b"])


# ------------------------------------------------------------- présentation

def test_les_plus_fortes_contributions_sortent_en_premier() -> None:
    """Tri sur la valeur ABSOLUE : une variable qui pousse fortement à la baisse
    explique autant qu'une qui pousse à la hausse."""
    lignes = contributions_lisibles(np.array([0.1, -0.9, 0.4]), ["a", "b", "c"])
    assert [x["variable"] for x in lignes] == ["b", "c", "a"]
    assert lignes[0]["sens"] == "pousse à la baisse"


def test_une_contribution_nulle_est_dite_sans_effet() -> None:
    lignes = contributions_lisibles(np.array([0.0]), ["a"])
    assert lignes[0]["sens"] == "sans effet"
