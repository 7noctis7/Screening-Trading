"""Audit d'inefficience : doit distinguer un marché à momentum d'une marche aléatoire."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from packages.data.inefficiency import inefficiency_report, variance_ratio


@dataclass
class Bar:
    ts: datetime
    close: float


def _series(n, kind, seed):
    rng = np.random.default_rng(seed)
    px, out = 100.0, []
    t0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
    prev = 0.0
    for i in range(n):
        if kind == "momentum":                       # rendements autocorrélés (trending)
            shock = rng.normal(0, 0.012)
            r = 0.45 * prev + shock
            prev = r
        else:                                        # marche aléatoire
            r = rng.normal(0.0003, 0.015)
        px *= math.exp(r)
        out.append(Bar(t0 + timedelta(days=i), px))
    return out


def _universe(kind, m=12, n=400):
    return {f"{kind}{i}": _series(n, kind, seed=i + (0 if kind == "rw" else 100)) for i in range(m)}


def test_variance_ratio_random_walk_near_one():
    rng = np.random.default_rng(0)
    r = rng.normal(0, 0.01, size=2000)
    assert abs(variance_ratio(r, 5) - 1.0) < 0.2


def test_momentum_universe_scores_higher_than_random_walk():
    rw = inefficiency_report(_universe("rw"))
    mo = inefficiency_report(_universe("momentum"))
    assert rw["available"] and mo["available"]
    # le marché à momentum doit montrer une autocorrélation nettement plus positive
    assert mo["autocorr_lag1"] > rw["autocorr_lag1"] + 0.1
    assert mo["score"] >= rw["score"]


def test_report_degrades_on_tiny_universe():
    assert inefficiency_report({"A": _series(50, "rw", 1)})["available"] is False
