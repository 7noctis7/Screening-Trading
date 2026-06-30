"""Tests des correctifs d'audit : DSR/ledger, MinTRL, Roll spread, sabotage sweep."""

import numpy as np

from packages.portfolio.psr import min_track_record_length
from packages.research.adversarial import roll_spread, sabotage_sweep
from packages.research.ledger import deflation_params


def test_deflation_params(tmp_path):
    from packages.research.ledger import append_record
    p = tmp_path / "h.jsonl"
    for s in (0.2, 0.8, 1.4):
        append_record({"facteur": "x", "sharpe": s}, path=p)
    n, sr_std = deflation_params(path=p)
    assert n == 3 and sr_std > 0          # N = nb d'essais, sr_std estimé inter-essais
    # ledger vide → repli propre (N=min_trials, sr_std=1)
    n2, s2 = deflation_params(path=tmp_path / "vide.jsonl", min_trials=9)
    assert n2 == 9 and s2 == 1.0


def test_min_track_record_length():
    # plus le Sharpe est faible, plus il faut d'observations pour y croire
    short = min_track_record_length(2.0)
    long = min_track_record_length(0.5)
    assert long > short > 0
    assert min_track_record_length(0.0) == float("inf")     # SR ≤ benchmark → jamais


def test_roll_spread_positive_on_bid_ask_bounce():
    # rebond bid-ask (autocovariance négative) → spread implicite > 0
    rng = np.random.default_rng(0)
    mid = 100 + np.cumsum(rng.normal(0, 0.01, 300))
    bounce = mid + np.where(rng.random(300) > 0.5, 0.05, -0.05)   # ±demi-spread
    assert roll_spread(bounce) > 0
    assert roll_spread([1, 2]) == 0.0


def test_sabotage_sweep_curve_and_breakeven():
    rng = np.random.default_rng(1)
    good = rng.normal(0.002, 0.01, 300)        # edge net positif
    out = sabotage_sweep(good)
    assert out["available"] and len(out["curve"]) == 4
    assert all("retention" in c for c in out["curve"])
    # rétention décroît avec le stress
    rets = [c["retention"] for c in out["curve"]]
    assert rets[0] >= rets[-1]
