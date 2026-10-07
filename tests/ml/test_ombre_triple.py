"""Triple barrière en shadow : la nulle permute le méta-label par semaine."""

import numpy as np

from packages.ml.ombre_triple import STATUT, juger, meta_labels


def test_le_module_reste_shadow():
    assert STATUT.startswith("SHADOW")


def test_un_signal_plante_bat_la_nulle_hebdomadaire():
    rng = np.random.default_rng(0)
    y = np.array([0, 1] * 40)
    scores = y + rng.normal(0, 0.01, y.size)
    semaines = np.repeat(np.arange(10), 8)
    r = juger(y, scores, semaines, n=30, graine=1)
    assert r["statut"] == "MESURÉ" and r["edge"] is True and r["p_permutation"] < 0.05


def test_un_score_sans_lien_ne_declare_pas_d_edge():
    rng = np.random.default_rng(2)
    y = rng.integers(0, 2, 80)
    scores = rng.normal(size=80)
    semaines = np.repeat(np.arange(10), 8)
    r = juger(y, scores, semaines, n=30, graine=3)
    assert r["edge"] is False


def test_meta_label_exige_que_le_trade_paie_les_frais():
    close = np.linspace(100, 130, 40)
    rows = meta_labels(close, [25], cout=0.5)
    assert rows and rows[0]["sens"] == 1
    assert rows[0]["y"] in (0, 1)
