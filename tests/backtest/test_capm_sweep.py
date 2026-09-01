"""Le t de l'alpha — ce qui manquait pour lire « alpha annualisé 1,1 % ».

Un alpha ne veut rien dire tant qu'on ignore s'il est distinguable de zéro. Le
dashboard affichait 1,1 % sans son t ; le sweep de la part de cœur affichait Sharpe et
Sortino sans alpha du tout.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.index_core_sweep import _capm  # noqa: E402


def _courbe(rendements):
    eq, v = [100.0], 100.0
    for r in rendements:
        v *= 1 + r
        eq.append(v)
    return eq


def test_une_variante_IDENTIQUE_a_la_reference_a_un_alpha_NUL():
    """Contrôle intégré : à 100 % de cœur, la variante EST la référence."""
    import numpy as np
    r = list(np.random.default_rng(0).normal(0.0004, 0.01, 500))
    d = _capm(_courbe(r), _courbe(r))
    assert d["alpha_annual"] == pytest.approx(0.0, abs=1e-9)
    assert d["t_alpha"] == pytest.approx(0.0, abs=1e-6)
    assert d["beta"] == pytest.approx(1.0, abs=1e-9)


def test_un_alpha_REEL_est_retrouve_SANS_BIAIS():
    """On injecte 2 points de base par jour d'alpha pur : il doit ressortir.

    Et cela ne se teste pas sur UN tirage : l'erreur-type de l'alpha annualisé vaut
    ici ~0,026, si bien qu'un seul échantillon sort couramment à 0,09 pour une vraie
    valeur de 0,050. C'est la MÉDIANE sur plusieurs tirages qui doit tomber juste —
    exiger la justesse d'un tirage isolé testerait la chance du seed."""
    import numpy as np
    vise = 0.0002 * 252
    alphas, ts, betas = [], [], []
    for seed in range(12):
        rng = np.random.default_rng(seed)
        ref = rng.normal(0.0003, 0.01, 1500)
        var = 0.8 * ref + rng.normal(0.0002, 0.004, 1500)   # bêta 0,8 + alpha
        d = _capm(_courbe(list(var)), _courbe(list(ref)))
        alphas.append(d["alpha_annual"])
        ts.append(d["t_alpha"])
        betas.append(d["beta"])
    assert float(np.median(betas)) == pytest.approx(0.8, abs=0.02)
    assert float(np.median(alphas)) == pytest.approx(vise, abs=0.02)
    assert float(np.median(ts)) > 1.5


def test_du_BETA_PUR_ne_produit_aucun_alpha_significatif():
    """Contre-épreuve, sans laquelle le test précédent ne prouverait rien : une variante
    qui n'est que du marché amplifié ne doit PAS afficher d'alpha significatif."""
    import numpy as np
    rng = np.random.default_rng(2)
    ref = rng.normal(0.0003, 0.01, 1500)
    d = _capm(_courbe(list(1.3 * ref)), _courbe(list(ref)))
    assert d["beta"] == pytest.approx(1.3, abs=0.05)
    assert abs(d["t_alpha"]) < 2.0


def test_un_echantillon_trop_court_ne_renvoie_rien():
    assert _capm(_courbe([0.001] * 10), _courbe([0.001] * 10)) == {}


def test_une_reference_PLATE_ne_divise_pas_par_zero():
    assert _capm(_courbe([0.001] * 100), _courbe([0.0] * 100)) == {}
