"""Décomposition de la rotation : additive, bien attribuée, allers-retours comptés."""

import pytest

from packages.research.rotation_causes import agreger, decomposer


def _somme(d):
    return d["selection"] + d["echelle"] + d["redistribution"]


def test_un_nom_remplace_est_de_la_selection():
    d = decomposer({"A": 0.5, "B": 0.5}, {"A": 0.5, "C": 0.5})
    assert d["selection"] == pytest.approx(1.0) and d["echelle"] == 0
    assert d["redistribution"] == 0
    assert d["entres"] == ["C"] and d["sortis"] == ["B"]


def test_baisse_d_exposition_est_de_l_echelle():
    d = decomposer({"A": 0.5, "B": 0.5}, {"A": 0.25, "B": 0.25})
    assert d["echelle"] == pytest.approx(0.5)
    assert d["redistribution"] == pytest.approx(0)


def test_reponderation_a_somme_constante_est_de_la_redistribution():
    d = decomposer({"A": 0.5, "B": 0.5}, {"A": 0.6, "B": 0.4})
    assert d["redistribution"] == pytest.approx(0.2) and d["echelle"] == 0


@pytest.mark.parametrize("w0, w1", [
    ({"A": 0.3, "B": 0.3, "C": 0.2}, {"A": 0.1, "B": 0.4, "D": 0.3}),
    ({}, {"A": 0.5}), ({"A": 0.5}, {}),
    ({"A": 0.2, "B": 0.6}, {"A": 0.5, "B": 0.1}),
])
def test_additif_exactement(w0, w1):
    d = decomposer(w0, w1)
    assert _somme(d) == pytest.approx(d["total"]) and d["redistribution"] >= -1e-12


def test_agregat_parts_et_allers_retours():
    seq = [("j0", {"A": 0.5, "B": 0.5}),
           ("j1", {"A": 0.5, "C": 0.5}),      # B sort
           ("j2", {"A": 0.5, "B": 0.5}),      # B revient aussitôt : aller-retour
           ("j3", {"A": 0.25, "B": 0.25}),    # échelle
           ("j4", {})]                        # décision vide
    r = agreger(seq)
    assert r["allers_retours"] == 1 and r["decisions_vides"] == 1
    assert r["n_entrees"] == 2 and r["n_sorties"] == 4
    assert sum(r[f"part_{c}"] for c in ("selection", "echelle", "redistribution")) \
        == pytest.approx(1.0)
    assert r["total"] == pytest.approx(1.0 + 1.0 + 0.5 + 0.5)
