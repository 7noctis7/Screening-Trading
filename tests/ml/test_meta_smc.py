"""Méta-labellisation de SMCLXTP-A — ce qui doit tenir pour que le filtre ne mente pas.

Le ML ne choisit pas le sens (le signal primaire le fait), il décide d'AGIR ou non. Il
n'a le droit de filtrer que s'il bat une distribution NULLE (labels permutés) : sur du
bruit, pas de filtre, et pas de seuil « 0,65 » posé par principe.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.core.models import Bar
from packages.ml.meta_smc import (
    FEATURES,
    MetaFiltre,
    Reglages,
    analyser,
    auc,
    etiqueter,
    features,
    seuil_hors_echantillon,
    valider,
)

RAPIDE = Reglages(swing_length=5, pivot_length=5, horizon=10, n_plis=4,
                  n_permutations=20, modele="logit", min_evenements=40)


def _bars(c, graine=0, sym="X"):
    rng = np.random.default_rng(graine)
    c = np.asarray(c, float)
    h = c * (1 + rng.uniform(0.001, 0.01, c.size))
    lo = c * (1 - rng.uniform(0.001, 0.01, c.size))
    d0 = datetime(2018, 1, 1, tzinfo=UTC)
    return [Bar(sym, "1d", d0 + timedelta(days=i), c[i], h[i], lo[i], c[i], 1e6)
            for i in range(c.size)]


def _marche(n=600, graine=0, sym="X"):
    rng = np.random.default_rng(graine)
    return _bars(100 * np.exp(np.cumsum(rng.normal(0, 0.015, n))), graine, sym)


# ------------------------------------------------------------------ AUC

def test_auc_par_les_rangs():
    assert auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0
    assert auc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) == 0.5          # égalités
    assert np.isnan(auc([1, 1], [0.2, 0.3]))


# ------------------------------------------------------------------ features

def test_features_causales():
    bars = _marche()
    complet = features(bars, RAPIDE)
    assert set(complet) == set(FEATURES)
    for t in range(150, 600, 37):
        tronque = features(bars[:t + 1], RAPIDE)
        for nom in FEATURES:
            np.testing.assert_allclose(complet[nom][:t + 1], tronque[nom],
                                       equal_nan=True, err_msg=f"{nom} à t={t}")


def test_features_sans_unite_de_prix():
    bars = _marche()
    x7 = [Bar(b.instrument, b.timeframe, b.ts, 7 * b.open, 7 * b.high, 7 * b.low,
              7 * b.close, b.volume) for b in bars]
    a, b = features(bars, RAPIDE), features(x7, RAPIDE)
    for nom in FEATURES:
        np.testing.assert_allclose(a[nom], b[nom], rtol=1e-7, equal_nan=True, err_msg=nom)


# ------------------------------------------------------------------ labels

def test_triple_barriere_en_multiples_d_atr():
    montee = np.concatenate([np.full(60, 100.0), np.linspace(100, 130, 40)])
    baisse = np.concatenate([np.full(60, 100.0), np.linspace(100, 70, 40)])
    for serie, attendu in ((montee, 1), (baisse, 0)):
        y, ret, t0, t1, garde = etiqueter(_bars(serie), [59], RAPIDE)
        assert garde.tolist() == [True] and y.tolist() == [attendu]
        assert t1[0] > t0[0]


def test_pas_d_etiquette_sur_un_avenir_incomplet():
    bars = _bars(np.full(80, 100.0))
    _, _, _, _, garde = etiqueter(bars, [40, 75], RAPIDE)
    assert garde.tolist() == [True, False]              # 75 + horizon 10 > 79


# ------------------------------------------------------------------ validation

def _jeu(n=400, planté=True, graine=1):
    rng = np.random.default_rng(graine)
    X = rng.normal(size=(n, 3))
    bruit = rng.normal(size=n)
    y = ((X[:, 0] + 0.5 * bruit) > 0).astype(int) if planté else (bruit > 0).astype(int)
    t0 = np.arange(n) * 3
    return X, y, t0, t0 + 5, np.where(y == 1, 0.02, -0.01)


def test_sur_du_bruit_pas_de_filtre():
    X, y, t0, t1, ret = _jeu(planté=False)
    v = valider(X, y, t0, t1, RAPIDE)
    assert v["edge"]["edge"] is False
    filtre = MetaFiltre.depuis(v, seuil_hors_echantillon(v["proba_oof"], y, ret))
    assert not filtre.calibre
    with pytest.raises(RuntimeError):
        filtre.autorise(0.9)


def test_un_edge_plante_est_detecte_et_filtre():
    X, y, t0, t1, ret = _jeu(planté=True)
    v = valider(X, y, t0, t1, RAPIDE)
    assert v["edge"]["edge"] is True and v["edge"]["p_permutation"] < 0.05
    s = seuil_hors_echantillon(v["proba_oof"], y, ret)
    assert s["disponible"] and s["evaluation"]["rend_moyen_filtre"] > s["evaluation"]["rend_moyen_tous"]
    filtre = MetaFiltre.depuis(v, s)
    assert filtre.calibre
    assert filtre.autorise(s["seuil"] + 0.01) and not filtre.autorise(s["seuil"] - 0.01)


def test_la_cv_purgee_ne_melange_pas_les_labels():
    from packages.ml.cv import PurgedKFold
    _, _, t0, t1, _ = _jeu()
    for tr, te in PurgedKFold(4, 0.01, label_horizon=15).split(t0, t1):
        lo, hi = t0[te].min(), t1[te].max()
        assert not ((t1[tr] >= lo) & (t0[tr] <= hi)).any()


# ------------------------------------------------------------------ bout en bout

def test_analyse_de_bout_en_bout_sur_des_marches_aleatoires():
    univers = {f"S{k}": _marche(n=500, graine=k, sym=f"S{k}") for k in range(8)}
    rapport = analyser(univers, RAPIDE)
    assert rapport["statut"] in {"UNCALIBRATED", "MESURÉ"}
    assert rapport["n_evenements"] > 0
    assert rapport["filtre_utilisable"] is False        # du bruit ne se filtre pas


def test_trop_peu_d_evenements():
    rapport = analyser({"S0": _marche(n=120)}, RAPIDE)
    assert rapport["statut"] == "UNCALIBRATED" and rapport["filtre_utilisable"] is False


def test_le_modele_par_defaut_lightgbm_passe_la_meme_chaine():
    pytest.importorskip("lightgbm")
    X, y, t0, t1, ret = _jeu(planté=True)
    v = valider(X, y, t0, t1, Reglages(horizon=10, n_plis=4, n_permutations=20))
    assert v["edge"]["edge"] is True
