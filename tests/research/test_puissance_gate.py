"""Puissance du gate : le seuil publié est bien celui que le DSR applique, ni plus ni moins."""
import math

import pytest

from packages.portfolio.psr import deflated_sharpe_ratio, probabilistic_sharpe_ratio
from packages.research.protocole_oos import SEUIL_DSR
from packages.research.puissance_gate import (
    annees_necessaires,
    sharpe_annuel_minimal,
    sharpe_minimal,
    tableau,
)


def test_un_seul_essai_le_dsr_est_le_psr():
    """Avant le 10/11 : `_norm_ppf(0)` ≈ −6 plaçait le seuil très bas, et un Sharpe NUL
    sortait à DSR 0,99 — « déployable » sans rien avoir montré."""
    assert deflated_sharpe_ratio(0.0, 1000, 1) == probabilistic_sharpe_ratio(0.0, 1000) == 0.5
    assert deflated_sharpe_ratio(-0.05, 1000, 1) < 0.5
    assert deflated_sharpe_ratio(0.10, 1000, 1) == probabilistic_sharpe_ratio(0.10, 1000)


def test_un_seul_essai_reste_le_cas_le_plus_facile():
    """La correction ne doit pas inverser l'ordre : chercher davantage coûte toujours."""
    assert deflated_sharpe_ratio(0.10, 1000, 1) > deflated_sharpe_ratio(0.10, 1000, 2)


def test_le_seuil_publie_est_la_frontiere_exacte_de_la_porte():
    s = sharpe_minimal(2520, 5000)
    assert s is not None
    assert deflated_sharpe_ratio(s, 2520, 5000) > SEUIL_DSR
    assert deflated_sharpe_ratio(s - 1e-4, 2520, 5000) <= SEUIL_DSR


def test_un_essai_donne_le_seuil_classique_de_student():
    """Un essai, rendements normaux : Sharpe par période ≈ 1,645 / √(n − 1)."""
    assert sharpe_minimal(2521, 1) == pytest.approx(1.645 / math.sqrt(2520), rel=0.02)


def test_plus_d_essais_exige_plus_et_plus_d_annees_exige_moins():
    assert sharpe_annuel_minimal(10, 5000) > sharpe_annuel_minimal(10, 50)
    assert sharpe_annuel_minimal(20, 5000) < sharpe_annuel_minimal(5, 5000)


def test_les_annees_necessaires_inversent_bien_le_seuil():
    a = annees_necessaires(1.5, 5000)
    assert a is not None
    assert sharpe_annuel_minimal(a, 5000) == pytest.approx(1.5, abs=0.01)


def test_un_sharpe_nul_ou_trop_faible_n_est_jamais_reconnu():
    assert annees_necessaires(0.0, 5000) is None
    assert annees_necessaires(0.05, 5000, maximum=20.0) is None


def test_le_tableau_porte_les_deux_portes_et_son_hypothese():
    t = tableau(5000)
    assert set(t["sharpe_annuel_minimal"]) == {"promouvable", "déployable"}
    assert (t["sharpe_annuel_minimal"]["déployable"][10]
            > t["sharpe_annuel_minimal"]["promouvable"][10])
    assert "normaux" in t["hypothese"]
