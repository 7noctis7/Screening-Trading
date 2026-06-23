"""Tests du lignage & de la réconciliation de données (gouvernance)."""

from packages.data.lineage import fingerprint, reconcile


def test_fingerprint_is_order_invariant_and_deterministic():
    a = fingerprint("AAPL", "yf", ["2024-01-01", "2024-01-02"], [100.0, 101.0])
    b = fingerprint("AAPL", "yf", ["2024-01-02", "2024-01-01"], [101.0, 100.0])
    assert a.sha256 == b.sha256          # invariant à l'ordre
    assert a.n_rows == 2
    assert a.start == "2024-01-01" and a.end == "2024-01-02"


def test_fingerprint_changes_with_content():
    a = fingerprint("AAPL", "yf", ["2024-01-01"], [100.0])
    b = fingerprint("AAPL", "yf", ["2024-01-01"], [100.5])
    assert a.sha256 != b.sha256


def test_reconcile_identical_series_ok():
    s = {"2024-01-01": 100.0, "2024-01-02": 101.0}
    out = reconcile(s, dict(s))
    assert out["ok"] and out["n_breaches"] == 0
    assert out["max_rel_div"] == 0.0 and out["n_overlap"] == 2


def test_reconcile_detects_divergence():
    a = {"2024-01-01": 100.0, "2024-01-02": 100.0}
    b = {"2024-01-01": 100.0, "2024-01-02": 102.0}   # +2% le 2e jour
    out = reconcile(a, b, tol=0.005)
    assert not out["ok"] and out["n_breaches"] == 1
    assert out["max_rel_div"] > 0.005


def test_reconcile_no_overlap_is_ok():
    out = reconcile({"2024-01-01": 1.0}, {"2024-02-01": 1.0})
    assert out["n_overlap"] == 0 and out["ok"]
