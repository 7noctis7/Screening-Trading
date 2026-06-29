"""Tests cassure de canal + gate — déterministe, hors-ligne (synthétique)."""

import numpy as np

from packages.research.breakout import (
    channel_break,
    detect_breakouts,
    significance,
)


def test_channel_break_detects_spike():
    base = list(100 + np.zeros(61))                 # 60 barres passées + barre courante
    base[-1] = 130                                  # pic net au-dessus du canal plat
    out = channel_break(base, win=60)
    assert out["price_break"] is True and out["break"] is True


def test_channel_break_requires_onchain_confirm():
    base = list(100 + np.zeros(61)); base[-1] = 130
    flat_conf = list(np.linspace(1, 2, 60)) + [1.5]   # variation mais PAS de pic final
    assert channel_break(base, win=60, confirm=flat_conf)["break"] is False
    conf = list(np.linspace(1, 2, 60)) + [50]         # pic on-chain franc à la fin
    assert channel_break(base, win=60, confirm=conf)["break"] is True


def test_too_short():
    assert channel_break([1, 2, 3], win=60)["break"] is False


def test_significance_runs_and_gates():
    rng = np.random.default_rng(0)
    px = 100 * np.cumprod(1 + rng.normal(0, 0.02, 400))
    out = significance(px.tolist(), win=40, post=5, n_sims=200, seed=1)
    assert "available" in out
    if out["available"]:
        assert out["verdict"] in ("SIGNIFICATIF", "BRUIT")
        assert 0.0 <= out["placebo_p_value"] <= 1.0


def test_detect_breakouts_causal_indices():
    px = list(100 + np.zeros(120))
    px[80] = 140                                    # une cassure isolée
    idx = detect_breakouts(px, win=40)
    assert all(i >= 40 for i in idx)
