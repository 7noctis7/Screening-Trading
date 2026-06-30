"""Tests résolution 3 étages + provenance (anti-cascade N/D)."""

from packages.data.resolve import resolve, uncertainty_mult, within_drop_budget


def test_resolve_tiers():
    assert resolve(1.5) == (1.5, "fresh")
    assert resolve(None, stale=1.2, stale_days=2) == (1.2, "stale:2d")
    v, p = resolve(None, None, peers=[1.0, 2.0, 3.0])
    assert v == 2.0 and p == "imputed_xs"
    assert resolve(None, None, peers=[1.0])[1] == "dropped"   # <3 pairs → drop
    assert resolve(None) == (None, "dropped")


def test_uncertainty_mult():
    assert uncertainty_mult("fresh") == 1.0
    assert uncertainty_mult("stale:3d") == (1 + 3) ** 0.5
    assert uncertainty_mult("imputed_xs") == 1.5
    assert uncertainty_mult("dropped") == float("inf")


def test_drop_budget():
    assert within_drop_budget(["fresh", "fresh", "stale:1d"]) is True
    assert within_drop_budget(["fresh", "imputed_xs", "imputed_xs", "imputed_xs"]) is False
    assert within_drop_budget([]) is False
