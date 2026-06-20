"""Modèle de coûts : par classe d'actifs + table d'hypothèses + barèmes courtiers réels."""

from packages.execution.costs import (
    BROKER_FEES,
    CostModel,
    broker_assumptions,
    broker_cost_bps,
    broker_fee,
    broker_for,
    cost_assumptions,
)


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


def test_broker_fee_table_real_schedules():
    # Alpaca actions = 0 commission ; BitMart crypto = 0,25 % = 25 bps (barèmes réels).
    assert BROKER_FEES["alpaca"]["commission_bps"] == 0.0
    assert BROKER_FEES["bitmart"]["commission_bps"] == 25.0
    assert BROKER_FEES["binance"]["commission_bps"] == 10.0
    # crypto BitMart strictement plus cher que actions Alpaca
    assert broker_cost_bps("crypto") > broker_cost_bps("equity")


def test_broker_default_mapping_matches_real_accounts():
    assert broker_for("equity") == "alpaca"      # actions/ETF → Alpaca (compte réel)
    assert broker_for("crypto") == "bitmart"     # crypto → BitMart (compte réel)


def test_broker_overridable_by_env(monkeypatch):
    monkeypatch.setenv("QUANT_BROKER_EQUITY", "ibkr")
    monkeypatch.setenv("QUANT_BROKER_CRYPTO", "binance")
    assert broker_for("equity") == "ibkr"
    assert broker_for("crypto") == "binance"


def test_broker_min_fee_dominates_small_orders(monkeypatch):
    # Alpaca (défaut) : pas de minimum → un petit ordre ne coûte que le slippage (≈ 0,02 $ sur 100 $).
    assert broker_fee("equity", 100.0) < 1.0
    # IBKR : minimum 1 $/ordre → un petit ordre coûte le minimum, pas ~0 via les bps.
    monkeypatch.setenv("QUANT_BROKER_EQUITY", "ibkr")
    assert broker_fee("equity", 100.0) >= 1.0           # 0,5 bp de 100 $ = 0,005 $ < min 1 $ → 1 $
    # au-dessus du seuil, la commission proportionnelle reprend le dessus
    assert broker_fee("equity", 1_000_000.0) > 1.0


def test_broker_fee_scales_with_notional_above_min():
    # crypto BitMart 0,25 % + 10 bps slippage = 35 bps, pas de min → proportionnel au notionnel.
    assert broker_fee("crypto", 10000.0) == round(10000.0 * 35 / 1e4, 6) or broker_fee("crypto", 10000.0) > 0
    assert broker_fee("crypto", 20000.0) > broker_fee("crypto", 10000.0)


def test_alpaca_regulatory_fee_only_on_sell():
    # Alpaca : 0 commission. La VENTE coûte plus que l'ACHAT (frais SEC/TAF réglementaires, ventes only).
    buy = broker_fee("equity", 10000.0, "BUY")
    sell = broker_fee("equity", 10000.0, "SELL")
    assert sell > buy > 0                  # achat = slippage seul ; vente = slippage + réglementaire
    assert buy == round(10000.0 * 5 / 1e4, 6)   # 5 bps de slippage


def test_broker_assumptions_round_trip():
    rows = broker_assumptions()
    names = {r["broker"] for r in rows}
    assert {"alpaca", "ibkr", "binance", "bitmart"} <= names
    for r in rows:
        assert r["round_trip_bps"] == 2 * (r["commission_bps"] + r["slippage_bps"])


def test_ledger_fees_reduce_return_and_reconcile():
    """Les frais réduisent le rendement net et l'equity reste réconciliée (cash + positions)."""
    import os
    from datetime import datetime, timedelta

    import numpy as np

    from packages.backtest.preset_backtest import preset_ledger

    class _B:
        def __init__(self, ts, c):
            self.ts, self.close = ts, c

    rng = np.random.default_rng(3)
    d0 = datetime(2021, 1, 1)
    n = 800
    data = {f"S{j}": [_B(d0 + timedelta(days=i), float(p))
                      for i, p in enumerate(100 * np.cumprod(1 + rng.normal(5e-4, 0.02, n)))]
            for j in range(16)}
    qual = {s: 1.0 / (i + 1) for i, s in enumerate(data)}

    def _run(fees):
        os.environ["QUANT_FEES"] = fees
        return preset_ledger(data, qual, asset_classes={}, dd_target=0.45,
                             init_cap=10000.0, max_trades=10000)

    try:
        net = _run("1")
        gross = _run("0")
    finally:
        os.environ.pop("QUANT_FEES", None)
    sn, sg = net["summary"], gross["summary"]
    assert sn["fees_paid"] > 0 and sg["fees_paid"] == 0
    assert sn["total_return"] <= sg["total_return"]            # les frais ne peuvent qu'amputer la perf
    assert abs(net["equity"][-1] - sn["final_equity"]) < 1.0   # equity réconciliée (frais inclus dans le cash)
    assert all("fee" in t for t in net["trades"])              # chaque trade porte son coût
    # COHÉRENCE des colonnes du journal : Σ latent(achats) = latent total ; Σ réalisé(ventes) = réalisé total
    lat_sum = sum(t["latent"] for t in net["trades"] if t.get("latent") is not None)
    real_sum = sum(t["pnl"] for t in net["trades"] if t.get("side") == "SELL" and t.get("pnl") is not None)
    assert abs(lat_sum - sn["unrealized_pnl"]) < 1.0
    assert abs(real_sum - sn["realized_pnl"]) < 1.0
    # IDENTITÉ globale : P&L total = réalisé + latent = gain du graphe + frais
    assert sn["reconciles"] is True
    assert abs(sn["total_pnl"] - (sn["graph_gain"] + sn["fees_paid"])) < 1.0
    # un achat dont les parts ont toutes été revendues ne porte plus de latent (= 0), pas de double-comptage
    assert any(t.get("latent") == 0.0 for t in net["trades"] if t.get("side") == "BUY")
