"""LightGBM était déclaré en dépendance et importé nulle part.

Une dépendance qu'on installe, qu'on met à jour, qu'on audite pour ses vulnérabilités —
et qui ne sert à rien. Le module matériel savait déjà lui parler
(`params_arbres("lightgbm")`) ; il ne manquait que l'adaptateur.

LightGBM n'est pas installé là où cette suite tourne, comme xgboost. Ce n'est pas une
gêne mais la bonne contrainte : elle force à vérifier le CÂBLAGE — les paramètres
réellement transmis — plutôt que le comportement de la bibliothèque, qui est testé chez
ses auteurs. On injecte donc un faux module qui enregistre ce qu'on lui passe.

LE POINT SUBTIL, ET LA RAISON PRINCIPALE DE CE FICHIER
LightGBM fait croître ses arbres PAR FEUILLE, XGBoost par NIVEAU. Laisser le défaut
`num_leaves=31` avec `max_depth=3` donnerait un arbre bien plus complexe que celui
d'XGBoost à réglages « identiques » : on croirait comparer deux algorithmes, on
comparerait deux capacités de mémorisation. Un arbre de profondeur 3 a au plus 2³ = 8
feuilles, d'où `num_leaves=7`.
"""

from __future__ import annotations

import sys
import types

import pytest

from packages.common import device as dev
from packages.ml.model import SklearnModel, make_model


class _FauxLGBM:
    """Enregistre les paramètres reçus. Assez « sklearn » pour traverser le Pipeline."""

    def __init__(self, **kw):
        self.kw = kw
        self._estimator_type = "classifier"

    def get_params(self, deep=True):
        return dict(self.kw)

    def set_params(self, **kw):
        self.kw.update(kw)
        return self

    def fit(self, X, y):
        return self


@pytest.fixture
def faux_lightgbm(monkeypatch):
    module = types.ModuleType("lightgbm")
    module.LGBMClassifier = _FauxLGBM
    monkeypatch.setitem(sys.modules, "lightgbm", module)
    dev.get_optimal_device.cache_clear()
    monkeypatch.delenv("QUANT_DEVICE", raising=False)
    yield module
    dev.get_optimal_device.cache_clear()


def _params(modele) -> dict:
    return modele.pipe.named_steps["clf"].kw


def test_lightgbm_est_desormais_constructible(faux_lightgbm) -> None:
    """Avant : `make_model("lightgbm")` levait « modèle inconnu »."""
    assert isinstance(make_model("lightgbm"), SklearnModel)


def test_le_nombre_de_feuilles_suit_la_profondeur(faux_lightgbm) -> None:
    """LE test. Sans ça, on croirait comparer deux algorithmes en comparant deux
    capacités de mémorisation : profondeur 3 → au plus 8 feuilles, pas 31."""
    p = _params(make_model("lightgbm"))
    assert p["max_depth"] == 3
    assert p["num_leaves"] <= 2 ** p["max_depth"], (
        f"num_leaves={p['num_leaves']} pour une profondeur de {p['max_depth']} : "
        "l'arbre peut mémoriser bien plus que son équivalent XGBoost, et la "
        "comparaison entre les deux ne veut plus rien dire."
    )


def test_les_reglages_sont_alignes_sur_xgboost(faux_lightgbm) -> None:
    """Comparer deux algorithmes exige de ne changer QU'UNE chose à la fois."""
    p = _params(make_model("lightgbm"))
    assert p["n_estimators"] == 100, "nombre d'arbres différent d'XGBoost"


def test_la_graine_est_posee(faux_lightgbm) -> None:
    """Même exigence que pour les autres modèles : deux exécutions doivent coïncider,
    sinon on ne pourra comparer ni deux versions du code, ni deux machines."""
    assert _params(make_model("lightgbm"))["random_state"] == SklearnModel.GRAINE


def test_les_journaux_ne_sont_pas_noyes(faux_lightgbm) -> None:
    """Sans `verbose=-1`, LightGBM écrit à chaque ajustement — une validation croisée
    à cinq plis en devient illisible."""
    assert _params(make_model("lightgbm"))["verbose"] == -1


def test_aucun_gpu_n_est_impose_sur_processeur(faux_lightgbm, monkeypatch) -> None:
    """`pip install lightgbm` livre une version SANS GPU : réclamer `device_type=gpu`
    dessus lèverait à l'entraînement, au milieu d'un calcul long."""
    monkeypatch.setattr(dev, "_torch", lambda: None)
    assert "device_type" not in _params(make_model("lightgbm"))


def test_le_gpu_est_demande_si_le_binaire_le_sait(faux_lightgbm, monkeypatch) -> None:
    """Contrôle négatif du test précédent : si le GPU n'était JAMAIS demandé, le
    branchement matériel serait décoratif."""
    monkeypatch.setenv("QUANT_DEVICE", "cuda")
    dev.get_optimal_device.cache_clear()
    monkeypatch.setattr(dev, "_lightgbm_gpu", lambda: True)
    assert _params(make_model("lightgbm"))["device_type"] == "gpu"


def test_un_modele_inconnu_leve_toujours() -> None:
    with pytest.raises(ValueError, match="modèle inconnu"):
        make_model("reseau_de_neurones_magique")
