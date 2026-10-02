"""La nulle de l'onglet ML se permute par date, ou elle dit qu'elle n'a rien testé."""

from pathlib import Path

import numpy as np

from packages.ml.distribution_nulle import (
    calculer_nulles,
    compter_dates,
    permuter_par_date,
    servir_nulles,
)
from packages.ml.validation_edge import edge_detecte


def _auc(scores, y) -> float:
    y = np.asarray(y, float)[np.argsort(scores)]
    n_pos, n = y.sum(), len(y)
    n_neg = n - n_pos
    numerateur = np.arange(1, n + 1)[y == 1].sum() - n_pos * (n_pos + 1) / 2
    return float(numerateur / (n_pos * n_neg))


def _panel(n_dates=40, n_noms=10):
    dates = np.repeat(np.arange(n_dates), n_noms)
    y = np.tile(np.array([0.0, 1.0] * (n_noms // 2)), n_dates)
    return y.copy(), y, dates


def test_une_ligne_par_date_ne_permute_rien():
    y = np.array([0, 1, 0, 1])
    dates = np.array([1, 2, 3, 4])
    mel, fig, con = compter_dates(y, dates)
    assert (mel, fig, con) == (0, 4, 0)
    r = calculer_nulles(y, dates, lambda _yp: [0.9])
    assert r["auc_nulles"] == [] and r["n_essais"] == 0


def test_la_permutation_conserve_le_taux_de_chaque_date():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, 200)
    dates = np.repeat(np.arange(20), 10)
    yp = permuter_par_date(y, dates, np.random.default_rng(2))
    assert not np.array_equal(y, yp)
    for d in np.unique(dates):
        assert y[dates == d].sum() == yp[dates == d].sum()


def test_un_signal_intra_date_bat_la_nulle_un_signal_de_jour_non():
    x, y, dates = _panel()
    assert _auc(x, y) == 1.0

    def evaluer(y_perm):
        return [_auc(x, y_perm)]

    r = calculer_nulles(y, dates, evaluer, n=20, graine=7)
    assert r["n_rendues"] == 20
    assert r["dates_contrastables"] == 40
    assert float(np.mean(r["auc_nulles"])) < 0.65
    assert edge_detecte([1.0, 1.0, 1.0], r["auc_nulles"])["edge"] is True


def test_sans_activation_evaluer_n_est_pas_appele_et_l_artefact_est_relu():
    def evaluer(_y):
        raise AssertionError("l'API ne doit pas recalculer les nulles")

    absent = servir_nulles(y=[0, 1], dates=[1, 1], evaluer=evaluer,
                            stockees=None, activer=False)
    assert absent["source"] == "absente" and absent["auc_nulles"] is None
    stocke = {"auc_nulles": [0.5] * 20, "dates_contrastables": 4, "dates_melangees": 4}
    relu = servir_nulles(y=[0, 1], dates=[1, 1], evaluer=evaluer,
                          stockees=stocke, activer=False)
    assert relu["source"] == "artefact" and relu["auc_nulles"] == stocke["auc_nulles"]


def test_labels_identiques_dans_la_date_comptent_zero():
    y = np.array([1, 1, 0, 0])
    dates = np.array([1, 1, 2, 2])
    assert compter_dates(y, dates) == (2, 0, 0)
    r = calculer_nulles(y, dates, lambda _yp: [0.99])
    assert r["auc_nulles"] == [] and r["dates_contrastables"] == 0


def test_make_train_pose_la_nulle_avant_d_entrainer():
    src = (Path(__file__).resolve().parents[2] / "scripts" / "train_model.py").read_text()
    pose = src.index('os.environ["QUANT_ML_NULLES"] = "1"')
    appel = src.index("ml = _ml_section(")
    assert pose < appel


def test_la_section_ml_sert_les_nulles_au_garde_fou():
    racine = Path(__file__).resolve().parents[2]
    bloc = (racine / "apps/api/snapshot.py").read_text().split("def _ml_section", 1)[1]
    bloc = bloc.split("\ndef ", 1)[0]
    assert "servir_nulles(" in bloc
    assert 'edge_detecte(aucs, _nulles.get("auc_nulles")' in bloc
    assert "QUANT_ML_NULLES" in bloc
    page = (racine / "apps/web/app/ml/page.tsx").read_text()
    assert "dates_contrastables" in page


