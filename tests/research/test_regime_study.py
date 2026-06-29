"""Tests étude de régime F&G — déterministe, hors-ligne (données synthétiques)."""

import numpy as np

from packages.research.regime_study import _returns, run_fng_study


def test_returns_basic():
    r = _returns([100.0, 110.0, 99.0])
    assert abs(r[1] - 0.1) < 1e-9 and abs(r[2] - (-0.1)) < 1e-9
    assert r[0] == 0.0


def test_too_short_is_unavailable():
    fng = [(f"2020-01-{i:02d}", 50.0) for i in range(1, 10)]
    btc = [(f"2020-01-{i:02d}", 100.0 + i) for i in range(1, 10)]
    out = run_fng_study(fng, btc)
    assert out["available"] is False


def test_runs_and_returns_verdict_on_synthetic():
    # 200 jours : F&G sinusoïdal, prix aléatoire → doit tourner et rendre un verdict.
    rng = np.random.default_rng(0)
    n = 200
    dates = [f"d{i:04d}" for i in range(n)]
    fvals = [50.0 + 40.0 * np.sin(i / 7.0) for i in range(n)]
    px = 100.0 * np.cumprod(1 + rng.normal(0, 0.02, n))
    out = run_fng_study(list(zip(dates, fvals)), list(zip(dates, px.tolist())),
                        n_sims=200, seed=1)
    assert out["available"] is True
    assert out["factor"] == "fear_greed_contrarian" and out["asset"] == "BTC"
    assert out["verdict"] in ("SIGNIFICATIF", "BRUIT")
    assert 0.0 <= out["placebo_p_value"] <= 1.0
