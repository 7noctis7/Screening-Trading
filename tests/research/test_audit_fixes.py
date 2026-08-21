"""Tests des correctifs d'audit : DSR/ledger, MinTRL, Roll spread, sabotage sweep."""

import numpy as np

from packages.portfolio.psr import min_track_record_length
from packages.research.adversarial import roll_spread, sabotage_sweep
from packages.research.ledger import deflation_params


def test_deflation_params(tmp_path):
    """Contrat CHANGÉ le 2026-08-20 (ADR-0035) : un Sharpe sans périodicité est EXCLU.

    Avant, `sr_std` mêlait des Sharpe annualisés à des Sharpe par période, ce qui plaçait le
    seuil du DSR à un Sharpe annualisé de ~27 — inatteignable par construction.
    """
    from packages.research.ledger import append_record
    p = tmp_path / "h.jsonl"
    # 3 facteurs DISTINCTS, périodicité INCONNUE → N=3, mais sr_std refuse de conclure
    for f, s in (("a", 0.2), ("b", 0.8), ("c", 1.4)):
        append_record({"facteur": f, "sharpe": s}, path=p)
    n, sr_std = deflation_params(path=p)
    assert n == 3 and sr_std is None          # repli √(1/n), falsifiable
    # avec la périodicité, les mêmes essais redeviennent exploitables
    p2 = tmp_path / "h2.jsonl"
    for f, s in (("a", 0.2), ("b", 0.8), ("c", 1.4)):
        append_record({"facteur": f, "sharpe": s, "periods_per_year": 12}, path=p2)
    n2, sr2 = deflation_params(path=p2)
    assert n2 == 3 and sr2 is not None and sr2 > 0
    # relancer le MÊME facteur 5× ne gonfle PAS N (essais ≠ runs)
    for _ in range(5):
        append_record({"facteur": "a", "sharpe": 0.3, "periods_per_year": 12}, path=p2)
    assert deflation_params(path=p2)[0] == 3  # toujours 3 hypothèses distinctes
    # ledger vide → sr_std=None (le DSR replie alors sur √(1/n), falsifiable — fix audit 07/15)
    assert deflation_params(path=tmp_path / "vide.jsonl", min_trials=9) == (9, None)


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
