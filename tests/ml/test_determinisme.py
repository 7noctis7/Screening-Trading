"""Deux exécutions du même code sur les mêmes données doivent coïncider.

Constaté le 07/09 en cherchant à prouver une non-régression : `scripts/demo_ml.py`
rendait 0,425 puis 0,382 d'un appel à l'autre. La différence ne venait pas du
changement testé — elle venait du script lui-même.

CAUSE, mesurée et non supposée. `GradientBoostingClassifier` était instancié sans
`random_state`. scikit-learn tire alors du générateur aléatoire GLOBAL de numpy pour
départager les égalités entre découpes d'arbre. Vérifié : figer ce générateur global
rendait la séquence reproductible, ce qui a isolé la cause.

CORRECTIF. La graine est posée sur l'ESTIMATEUR, jamais par `np.random.seed()` : figer
le générateur global depuis une bibliothèque contaminerait tout le processus, y compris
des tirages qui doivent rester indépendants.

POURQUOI ÇA COMPTE MAINTENANT. Un banc dont deux exécutions ne coïncident pas ne peut
comparer NI deux versions du code, NI deux machines. C'est exactement ce qui manquerait
au moment de valider la migration Mac (MPS) → NVIDIA (CUDA), où il faut pouvoir
distinguer un écart de matériel d'un écart de logique.
"""

from __future__ import annotations

import numpy as np

from packages.ml import make_model, purged_cv_score
from packages.ml.model import SklearnModel


def _echantillon(n: int = 400, d: int = 6):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(n, d))
    y = (rng.random(n) > 0.5).astype(int)
    return X, y, np.arange(n), np.arange(n) + 20


def test_la_validation_croisee_rend_deux_fois_le_meme_resultat() -> None:
    X, y, t0, t1 = _echantillon()
    scores = [purged_cv_score(lambda: make_model("sklearn"), X, y, t0, t1, n_splits=5)
              for _ in range(3)]
    assert len({str(s) for s in scores}) == 1, (
        f"trois appels identiques donnent des scores différents : {scores}. "
        "Le banc ne peut plus comparer ni deux versions, ni deux machines."
    )


def test_l_estimateur_par_defaut_porte_une_graine() -> None:
    """Sans graine explicite, scikit-learn retombe sur le générateur global."""
    est = SklearnModel().pipe.named_steps["clf"]
    assert est.random_state is not None, (
        "l'estimateur par défaut n'a plus de `random_state` : il consommera de nouveau "
        "le générateur aléatoire global, et le banc redeviendra instable."
    )


def test_la_graine_reste_reglable() -> None:
    """Figer n'est pas rigidifier : on doit pouvoir mesurer la SENSIBILITÉ à la graine,
    sinon on confond « reproductible » et « robuste »."""
    assert SklearnModel(graine=7).pipe.named_steps["clf"].random_state == 7


def test_deux_graines_differentes_peuvent_differer() -> None:
    """Contrôle négatif du test précédent : si le résultat ne bougeait JAMAIS avec la
    graine, c'est que le paramètre ne serait pas branché."""
    X, y, _, _ = _echantillon(300, 5)
    a = SklearnModel(graine=0).fit(X, y).predict_proba(X)
    b = SklearnModel(graine=99).fit(X, y).predict_proba(X)
    assert a.shape == b.shape
    # On n'exige PAS qu'elles diffèrent (elles peuvent coïncider sur des données sans
    # égalités) — on exige seulement que le paramètre soit accepté et propagé.
    assert SklearnModel(graine=99).pipe.named_steps["clf"].random_state == 99
