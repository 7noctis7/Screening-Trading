"""Bande d'inaction adaptative — ce qui doit tenir avant de la mesurer sur données réelles.

La bande de production est fixe (0,5 % du capital). La bande adaptative arbitre le coût
d'un aller-retour contre l'écart de suivi : elle s'élargit avec le coût et avec la
volatilité du poids, et se resserre avec l'aversion à l'écart. Loi d'échelle attendue :
h ∝ (coût · variance)^(1/3). L'aversion n'est PAS calibrée : ces tests valident la
mathématique, pas le réglage.
"""

from __future__ import annotations

import math

import pytest


def test_loi_en_racine_cubique_du_cout():
    from packages.execution.bande_adaptative import demi_largeur
    h1 = demi_largeur(0.08, 0.30, 0.0005, aversion=1.0, plancher=0.0)
    h8 = demi_largeur(0.08, 0.30, 0.0040, aversion=1.0, plancher=0.0)
    assert h8 == pytest.approx(2.0 * h1, rel=1e-9)


def test_monotonie_volatilite_et_aversion():
    from packages.execution.bande_adaptative import demi_largeur
    base = demi_largeur(0.08, 0.30, 0.0005, aversion=1.0, plancher=0.0)
    assert demi_largeur(0.08, 0.60, 0.0005, aversion=1.0, plancher=0.0) > base
    assert demi_largeur(0.08, 0.30, 0.0005, aversion=8.0, plancher=0.0) == \
        pytest.approx(base / 2.0, rel=1e-9)


def test_valeur_de_reference():
    """w = 8 %, σ = 30 %, c = 5 pb, γ = 1 : s = w(1−w)σ, h = (3·c·s²/γ)^(1/3)."""
    from packages.execution.bande_adaptative import demi_largeur
    s = 0.08 * 0.92 * 0.30
    assert demi_largeur(0.08, 0.30, 0.0005, aversion=1.0, plancher=0.0) == \
        pytest.approx((3 * 0.0005 * s * s) ** (1 / 3), rel=1e-12)


@pytest.mark.parametrize("w, vol, cout", [(0.0, 0.3, 0.0005), (0.1, 0.0, 0.0005),
                                          (0.1, 0.3, 0.0), (0.1, float("nan"), 0.0005)])
def test_cas_degeneres_renvoient_le_plancher(w, vol, cout):
    from packages.execution.bande_adaptative import demi_largeur
    assert demi_largeur(w, vol, cout, aversion=1.0, plancher=0.001) == 0.001


def test_plafond():
    from packages.execution.bande_adaptative import demi_largeur
    assert demi_largeur(0.5, 3.0, 0.05, aversion=0.01, plancher=0.0, plafond=0.05) == 0.05


def test_aversion_invalide_refusee():
    from packages.execution.bande_adaptative import demi_largeur
    with pytest.raises(ValueError):
        demi_largeur(0.1, 0.3, 0.0005, aversion=0.0)


def test_bande_en_monnaie_respecte_le_minimum():
    from packages.execution.bande_adaptative import bande_monnaie
    assert bande_monnaie(0.0, 100_000.0, 0.3, 0.0005, aversion=1.0) == 100.0   # plancher 0,1 %
    assert bande_monnaie(0.0, 1_000.0, 0.3, 0.0005, aversion=1.0) == 5.0       # minimum 5 $
    b = bande_monnaie(0.08, 100_000.0, 0.30, 0.0005, aversion=1.0)
    assert 100.0 < b < 2_000.0


def test_volatilite_causale():
    """La volatilité à la date d ne lit que les cours ≤ d."""
    from packages.execution.bande_adaptative import vol_annuelle
    jours = [f"2024-01-{k:02d}" for k in range(1, 31)]
    prix = {j: 100.0 * (1.01 if k % 2 else 0.99) ** k for k, j in enumerate(jours)}
    v1 = vol_annuelle(prix, jours, "2024-01-25", fenetre=10)
    prix2 = {**prix, **{j: 1e6 for j in jours if j > "2024-01-25"}}
    assert v1 == vol_annuelle(prix2, jours, "2024-01-25", fenetre=10)
    assert v1 > 0
    assert math.isnan(vol_annuelle(prix, jours, "2024-01-03", fenetre=10))   # trop court
