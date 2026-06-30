"""Tests déviation de peg xStocks — purs, hors-ligne."""

import numpy as np

from packages.research.peg_study import classify, peg_deviation, run_study


def test_peg_deviation_and_classify():
    assert abs(peg_deviation(101, 100) - 0.01) < 1e-9
    assert peg_deviation(100, 0) is None
    assert classify(0.012) == "prime"
    assert classify(-0.012) == "décote"
    assert classify(0.001) == "aligné"
    assert classify(None) == "n/d"


def test_run_study_too_short():
    out = run_study([1, 2, 3], [1, 2, 3])
    assert out["available"] is False


def test_run_study_runs_and_gates():
    rng = np.random.default_rng(0)
    n = 200
    und = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))    # sous-jacent
    noise = rng.normal(0, 0.004, n)                       # déviation de peg bruitée
    tok = und * (1 + noise)
    out = run_study(tok.tolist(), und.tolist(), post=3, n_sims=200, seed=1)
    assert "available" in out
    if out["available"]:
        assert out["factor"] == "xstock_peg_reversion"
        assert out["verdict"] in ("SIGNIFICATIF", "BRUIT")
        assert 0.0 <= out["placebo_p_value"] <= 1.0
