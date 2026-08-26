"""Test de différence de Sharpe — et surtout : est-il CALIBRÉ ?

Un test statistique non calibré est pire qu'aucun test : il donne une autorité
chiffrée à une décision arbitraire. Le contrôle décisif n'est donc pas « la
formule tourne » mais « sous l'hypothèse nulle, rejette-t-il bien 5 % du
temps ». C'est ce que vérifie `test_calibration_sous_h0`, par Monte-Carlo.
"""

import math

import numpy as np
import pytest

from packages.research.sharpe_diff import (
    comparer,
    seuil_detectable,
    sharpe_periodique,
)


def _paire(n, mu_a, mu_b, sd, rho, rng):
    cov = [[sd**2, rho * sd * sd], [rho * sd * sd, sd**2]]
    z = rng.multivariate_normal([mu_a, mu_b], cov, n)
    return list(z[:, 0]), list(z[:, 1])


# --- socle ---------------------------------------------------------------------

def test_sharpe_periodique_simple():
    # écart-type nul → 0, pas un ratio infini (tolérance relative)
    assert sharpe_periodique([0.01] * 10) == 0.0
    assert sharpe_periodique([0.02, -0.01, 0.03, 0.00]) > 0


def test_echantillon_trop_court_refuse_de_conclure():
    """Sous 30 points l'asymptotique n'est pas calibrée : le DIRE, pas deviner."""
    out = comparer([0.01] * 10, [0.02] * 10, 12.0)
    assert out["disponible"] is False and "30" in out["raison"]


def test_series_identiques_donnent_delta_nul():
    """Cas dégénéré : ρ = 1 et Sharpe égaux → différence nulle, pas un échec."""
    rng = np.random.default_rng(1)
    r = list(rng.normal(0.01, 0.04, 200))
    out = comparer(r, r, 12.0)
    assert out["disponible"] and abs(out["delta"]) < 1e-9
    assert out["degenere"] is True
    assert out["verdict"] == "indiscernable"
    assert abs(out["correlation"] - 1.0) < 1e-9


# --- LE test qui compte --------------------------------------------------------

@pytest.mark.parametrize("rho", [0.99, 0.95, 0.0])
def test_calibration_sous_h0(rho):
    """MÊME Sharpe vrai → rejet attendu ~5 % du temps, quelle que soit ρ.

    Trop de rejets = on « découvre » des leviers qui n'existent pas. Trop peu =
    on rate ceux qui existent. La bande [3 %, 8 %] laisse la place à l'erreur de
    Monte-Carlo sur 800 tirages (écart-type ≈ 0,8 pt) sans laisser passer une
    formule franchement fausse.
    """
    rng = np.random.default_rng(7)
    n, sd, n_sim = 126, 0.04, 800
    mu = 1.35 / math.sqrt(12) * sd
    rejets = sum(
        comparer(*_paire(n, mu, mu, sd, rho, rng), 12.0)["verdict"] != "indiscernable"
        for _ in range(n_sim))
    taux = rejets / n_sim
    assert 0.03 <= taux <= 0.08, f"rho={rho} : {taux:.1%} sous H0 (attendu 5 %)"


def test_grand_ecart_est_detecte():
    """Contre-épreuve : un écart franc DOIT être vu, sinon le test ne sert à rien."""
    rng = np.random.default_rng(11)
    n, sd = 126, 0.04
    mu_a = 1.0 / math.sqrt(12) * sd
    mu_b = 2.5 / math.sqrt(12) * sd
    vus = sum(
        comparer(*_paire(n, mu_a, mu_b, sd, 0.95, rng), 12.0)["verdict"] == "meilleur"
        for _ in range(200))
    assert vus / 200 > 0.8


def test_verdict_pire_est_symetrique():
    rng = np.random.default_rng(13)
    n, sd = 126, 0.04
    a, b = _paire(n, 2.5 / math.sqrt(12) * sd, 1.0 / math.sqrt(12) * sd, sd, 0.95, rng)
    assert comparer(a, b, 12.0)["verdict"] in ("pire", "indiscernable")


# --- puissance : ce que le labo peut voir ---------------------------------------

def test_seuil_detectable_decroit_avec_la_correlation():
    """Deux variantes très corrélées sont plus faciles à départager — tout
    l'intérêt d'un test APPARIÉ plutôt que deux erreurs-types indépendantes."""
    assert seuil_detectable(126, 1.35, 0.99) < seuil_detectable(126, 1.35, 0.90)
    assert seuil_detectable(126, 1.35, 0.90) < seuil_detectable(126, 1.35, 0.50)


def test_seuil_detectable_decroit_avec_la_taille():
    assert seuil_detectable(500, 1.35, 0.95) < seuil_detectable(126, 1.35, 0.95)


def test_le_gate_a_005_est_sous_le_plancher_de_detection():
    """CONSTAT DOCUMENTÉ (25/08). Le labo promeut un levier à +0,05 de Sharpe.
    Sur 126 pas, même à ρ = 0,99, le plus petit écart détectable est ~+0,14 : le
    seuil du gate est TROIS FOIS sous ce que l'échantillon résout. À +0,05,
    promouvoir ou rejeter relève du tirage au sort. Si ce test casse, c'est que
    la fenêtre s'est allongée — vérifier alors si le seuil peut être abaissé en
    connaissance de cause."""
    assert seuil_detectable(126, 1.35, 0.99) > 0.05 * 2
