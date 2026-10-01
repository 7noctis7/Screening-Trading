"""P1.3 — coûts unifiés : barème courtier = source de vérité RT / CostModel / assumptions.

Parité Risk / TCA / ML via helper partagé `round_trip_bps(ac)` (sleeve OFF, paper-only).
"""

from __future__ import annotations

import pytest

from packages.execution.costs import (
    BROKER_FEES,
    CostModel,
    broker_assumptions,
    broker_charge,
    broker_fee,
    broker_for,
    cost_assumptions,
    cout_execution,
    round_trip_bps,
)


# ── barèmes documentés ──────────────────────────────────────────────────────

def test_equity_alpaca_round_trip_inclut_reg():
    """equity(alpaca) RT = 2×(0+5) + 0,28 = 10,28."""
    assert broker_for("equity") == "alpaca"
    assert round_trip_bps("equity") == pytest.approx(10.28)
    assert CostModel.for_asset_class("equity").round_trip_bps == pytest.approx(10.28)


def test_crypto_bitmart_round_trip():
    """crypto(bitmart) RT = 2×(25+12) + 0 = 74."""
    assert broker_for("crypto") == "bitmart"
    assert round_trip_bps("crypto") == pytest.approx(74.0)
    assert CostModel.for_asset_class("crypto").round_trip_bps == pytest.approx(74.0)


def test_costmodel_for_asset_class_derive_de_broker_fees():
    """fee_bps=commission, slippage_bps=slip, reg_bps=reg — plus de table retail divergente."""
    cm = CostModel.for_asset_class("equity")
    b = BROKER_FEES["alpaca"]
    assert cm.fee_bps == b["commission_bps"]
    assert cm.slippage_bps == b["slippage_bps"]
    assert cm.reg_bps == b["reg_bps"]


def test_costmodel_round_trip_property_inclut_reg():
    cm = CostModel(fee_bps=0.0, slippage_bps=5.0, reg_bps=0.28)
    assert cm.round_trip_bps == pytest.approx(10.28)


# ── parité helper / CostModel / assumptions ─────────────────────────────────

@pytest.mark.parametrize("ac", ["equity", "etf", "index", "crypto", "forex", "commodity"])
def test_round_trip_bps_bit_identique_costmodel_et_assumptions(ac):
    helper = round_trip_bps(ac)
    model = CostModel.for_asset_class(ac).round_trip_bps
    assert helper == pytest.approx(model)

    row = next(r for r in cost_assumptions() if r["asset_class"] == ac)
    assert row["round_trip_bps"] == pytest.approx(helper)
    assert row["fee_bps"] == CostModel.for_asset_class(ac).fee_bps
    assert row["slippage_bps"] == CostModel.for_asset_class(ac).slippage_bps
    assert row["reg_bps"] == CostModel.for_asset_class(ac).reg_bps

    broker = broker_for(ac)
    brow = next(r for r in broker_assumptions() if r["broker"] == broker)
    assert brow["round_trip_bps"] == pytest.approx(helper)


def test_broker_assumptions_inclut_reg_bps():
    alpaca = next(r for r in broker_assumptions() if r["broker"] == "alpaca")
    assert alpaca["round_trip_bps"] == pytest.approx(
        2 * (alpaca["commission_bps"] + alpaca["slippage_bps"]) + alpaca["reg_bps"])
    assert alpaca["round_trip_bps"] == pytest.approx(10.28)


# ── cout_execution wrapper ──────────────────────────────────────────────────

def test_cout_execution_mode_fee_vs_charge():
    n = 10_000.0
    assert cout_execution("equity", n, "BUY", mode="fee") == pytest.approx(
        broker_fee("equity", n, "BUY"))
    assert cout_execution("equity", n, "SELL", mode="charge") == pytest.approx(
        broker_charge("equity", n, "SELL"))
    # fee inclut slip ; charge non
    assert cout_execution("crypto", n, "BUY", mode="fee") > cout_execution(
        "crypto", n, "BUY", mode="charge")


def test_cout_execution_mode_inconnu():
    with pytest.raises(ValueError, match="mode"):
        cout_execution("equity", 100.0, "BUY", mode="wtf")


# ── parité smoke Risk / TCA / ML (3 call-sites) ─────────────────────────────

def test_parite_trois_call_sites_risk_tca_ml():
    """Simule Risk gate / TCA attribution / label coût ML — bit-identiques via helper."""

    def risk_gate_cost_bps(asset_class: str) -> float:
        return round_trip_bps(asset_class)

    def tca_attribution_cost_bps(asset_class: str) -> float:
        return round_trip_bps(asset_class)

    def ml_cost_label_bps(asset_class: str) -> float:
        return round_trip_bps(asset_class)

    for ac in ("equity", "crypto"):
        a = risk_gate_cost_bps(ac)
        b = tca_attribution_cost_bps(ac)
        c = ml_cost_label_bps(ac)
        assert a == b == c == round_trip_bps(ac)
        assert a == CostModel.for_asset_class(ac).round_trip_bps
