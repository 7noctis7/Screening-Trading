"""Tests lot 2 d'audit : BVC ECDF, PIT guard, bootstrap CI du Sharpe."""

from datetime import datetime

import numpy as np

from packages.common.pit_guard import assert_no_leak, pit_filter, stable_prefix
from packages.portfolio.psr import bootstrap_sharpe_ci
from packages.research.microstructure import bulk_buy_fraction_ecdf, vpin


def test_bvc_ecdf():
    sample = [-2.0, -1.0, 0.0, 1.0, 2.0]
    assert bulk_buy_fraction_ecdf(3.0, sample) == 1.0      # au-dessus de tout → 100% achat
    assert bulk_buy_fraction_ecdf(-3.0, sample) == 0.0     # en dessous → 0% achat
    assert bulk_buy_fraction_ecdf(0.5, sample) == 0.6      # rang médian-haut
    assert bulk_buy_fraction_ecdf(0.0, []) == 0.5


def test_vpin_ecdf_method_runs():
    up = [100.0]
    for i in range(80):
        up.append(up[-1] + (1.0 if i % 3 else 0.7))
    out = vpin(up, [10.0] * len(up), bucket=50, n_buckets=10, method="ecdf")
    assert out["available"] and out["vpin"] > 0.5


def test_pit_guard():
    d = lambda s: datetime.fromisoformat(s)  # noqa: E731
    recs = [{"v": 1, "realtime_start": d("2020-01-10")},
            {"v": 2, "realtime_start": d("2020-02-15")}]
    kept = pit_filter(recs, d("2020-01-31"))
    assert len(kept) == 1 and kept[0]["v"] == 1
    assert_no_leak(kept, d("2020-01-31"))                  # ok
    raised = False
    try:
        assert_no_leak(recs, d("2020-01-31"))              # la 2e est du futur
    except AssertionError:
        raised = True
    assert raised


def test_stable_prefix_detects_revision():
    assert stable_prefix([1, 2, 3, 4], [1, 2, 3]) is True
    assert stable_prefix([1, 2, 9, 4], [1, 2, 3]) is False  # le passé a changé → fuite


def test_bootstrap_sharpe_ci():
    rng = np.random.default_rng(0)
    pos = rng.normal(0.001, 0.01, 500)                     # Sharpe positif net
    out = bootstrap_sharpe_ci(pos, n_boot=300)
    assert out["available"] and out["lo"] < out["sharpe"] < out["hi"]
    assert 0.0 <= out["prob_positive"] <= 1.0
    assert bootstrap_sharpe_ci([0.0] * 5)["available"] is False
