"""Modèle de coûts : par classe d'actifs + table d'hypothèses."""

from packages.execution.costs import CostModel, cost_assumptions


def test_round_trip_bps():
    cm = CostModel(fee_bps=2.0, slippage_bps=3.0)
    assert cm.round_trip_bps == 10.0


def test_per_asset_class_differs():
    eq = CostModel.for_asset_class("equity")
    cr = CostModel.for_asset_class("crypto")
    assert cr.round_trip_bps > eq.round_trip_bps      # crypto plus cher que actions liquides


def test_unknown_class_falls_back_to_equity():
    assert CostModel.for_asset_class("zzz").round_trip_bps == CostModel.for_asset_class("equity").round_trip_bps


def test_cost_assumptions_table():
    rows = cost_assumptions()
    classes = {r["asset_class"] for r in rows}
    assert {"equity", "crypto", "forex"} <= classes
    for r in rows:
        assert r["round_trip_bps"] == 2 * (r["fee_bps"] + r["slippage_bps"])
