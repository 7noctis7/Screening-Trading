"""Le dashboard affichait « PSR 0,0 % · DSR 0,0 % » et en tirait « pas d'alpha prouvé ».

Les deux nombres étaient calculés sur un Sharpe de ZÉRO. Le code lisait :

    sr = rm.get("sharpe", 0.0) / sqrt(252) if rm.get("sharpe") else 0.0

et `risk_metrics()` ne renvoie PAS de clé `sharpe` — seulement var/cvar/vol. La clé
manquait donc toujours. Le défaut n'était pas la formule mais le CHEMIN DE LA DONNÉE :
un `.get()` avec valeur par défaut sur une clé absente ne lève rien, il ment.
"""

import math

import pytest

from packages.portfolio.psr import (
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    psr_dsr_depuis_rendements,
)


def _serie(sharpe_annualise: float, n: int = 2641, seed: int = 0):
    """Rendements quotidiens de Sharpe annualisé imposé."""
    import numpy as np
    r = np.random.default_rng(seed).normal(0.0, 0.01, n)
    cible = sharpe_annualise / math.sqrt(252)
    return list(r - r.mean() + cible * r.std(ddof=1))


def test_le_bug_exact_est_reproduit_puis_corrige():
    """Sur les chiffres du dashboard : Sharpe 0,96 annualisé, 2641 observations."""
    ancien_sr = 0.0                          # ce que la clé absente produisait
    assert probabilistic_sharpe_ratio(ancien_sr, 2641) == 0.5
    assert deflated_sharpe_ratio(ancien_sr, 2641, 20) < 0.05

    d = psr_dsr_depuis_rendements(_serie(0.96), n_trials=20)
    assert d["sharpe_annualise"] == pytest.approx(0.96, abs=0.01)
    assert d["psr"] > 0.99                             # et non 0,5
    assert d["dsr"] > 0.80                             # et non ~0,03


def test_un_sharpe_NUL_donne_bien_un_PSR_de_MOITIE():
    """Contre-épreuve : la formule n'est pas en cause, seule la donnée l'était."""
    d = psr_dsr_depuis_rendements(_serie(0.0, seed=3), n_trials=20)
    assert d["psr"] == pytest.approx(0.5, abs=0.02)


def test_le_DSR_baisse_quand_le_nombre_d_ESSAIS_monte():
    """Toute la raison d'être du DSR : le maximum de N Sharpe bruités croît en
    sqrt(2 ln N) — un même Sharpe vaut moins après cent tentatives qu'après vingt."""
    r = _serie(0.96)
    suite = [psr_dsr_depuis_rendements(r, n_trials=k)["dsr"]
             for k in (20, 50, 100, 500)]
    assert suite == sorted(suite, reverse=True)
    assert suite[0] > suite[-1]


def test_un_echantillon_insuffisant_est_ABSENT_et_non_ZERO():
    """La règle du dépôt : une valeur manquante ne se publie pas en chiffre."""
    for court in (None, [], [0.01] * 10):
        d = psr_dsr_depuis_rendements(court)
        assert d["available"] is False and "psr" not in d


def test_une_serie_PLATE_ne_divise_pas_par_zero():
    assert psr_dsr_depuis_rendements([0.0] * 100)["available"] is False


def test_un_ndarray_traverse_sans_lever():
    """`serie or []` lève « truth value ambiguous » sur un ndarray, et c'est
    exactement sous cette forme que les rendements arrivent."""
    np = pytest.importorskip("numpy")
    d = psr_dsr_depuis_rendements(np.asarray(_serie(0.96), dtype=float), n_trials=20)
    assert d["available"] and d["psr"] > 0.99


def test_les_points_non_finis_sont_ECARTES_et_non_propages():
    r = _serie(0.96) + [float("nan"), float("inf")]
    d = psr_dsr_depuis_rendements(r, n_trials=20)
    assert d["n_obs"] == 2641 and math.isfinite(d["psr"])
