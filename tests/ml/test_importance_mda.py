"""MDA par grappes : une variable informative tient hors échantillon, le bruit non,
et deux variables qui se substituent sont jugées ENSEMBLE (synthétique : valide la
mathématique seulement, AGENTS.md règle 3)."""

import numpy as np

from packages.ml import importance_mda as mda
from packages.ml.model import LogitModel


def _jeu(n=3000, graine=0):
    rng = np.random.default_rng(graine)
    signal = rng.normal(size=n)
    jumeau = signal + 0.2 * rng.normal(size=n)       # même information, corrélée
    bruit = rng.normal(size=n)
    y = (signal + 1.5 * rng.normal(size=n) > 0).astype(float)
    X = np.column_stack([signal, jumeau, bruit])
    T0 = np.arange(n) * 2
    return X, y, T0, T0 + 5


def test_les_jumeaux_forment_une_grappe_le_bruit_non():
    X, *_ = _jeu()
    assert mda.grappes(X) == [[0, 1], [2]]


def test_la_grappe_informative_tient_hors_echantillon_le_bruit_non():
    X, y, T0, T1 = _jeu()
    r = mda.mda_purge(X, y, T0, T1, lambda: LogitModel(epochs=200))
    par = {tuple(g["variables"]): g for g in r["grappes"]}
    assert par[(0, 1)]["mda"] > 0.05 and par[(0, 1)]["t"] > 3
    assert abs(par[(2,)]["mda"]) < 0.01
    assert len(r["auc_plis"]) == 5 and min(r["auc_plis"]) > 0.6


def test_sur_du_bruit_pur_aucune_grappe_ne_tient():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(3000, 4))
    y = (rng.normal(size=3000) > 0).astype(float)
    T0 = np.arange(3000) * 2
    r = mda.mda_purge(X, y, T0, T0 + 5, lambda: LogitModel(epochs=200))
    assert all(abs(g["mda"]) < 0.02 for g in r["grappes"])


def test_nommer():
    r = {"grappes": [{"variables": [0, 1], "mda": 0.1}]}
    assert mda.nommer(r, ["a", "b"])[0]["variables"] == ["a", "b"]
