"""Slippage réel mesuré (exec_costs) — journal SQLite temporaire, sans réseau."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.exec_costs import measured_slippage, sabotage_cost_bps
from packages.storage import SqliteTradeJournal


def _trade(i: int, decision: float, fill: float) -> TradeRecord:
    return TradeRecord(
        id=f"T{i}", instrument="AAPL", asset_class=AssetClass.EQUITY, venue="Alpaca",
        side=Side.LONG, qty=1.0, entry_ts=datetime(2026, 7, 1, tzinfo=timezone.utc),
        entry_price=fill, avg_price=fill, entry_reason="t",
        features_snapshot={"decision_price": decision})


def test_uncalibrated_below_min_n(tmp_path):
    j = SqliteTradeJournal(tmp_path / "j.db")
    for i in range(5):
        j.append(_trade(i, 100.0, 100.05), legacy=False)
    st = measured_slippage(j)
    assert st["available"] is False and st["status"] == "UNCALIBRATED" and st["n"] == 5
    assert sabotage_cost_bps(j) is None              # pas de reco inventée


def test_stats_on_sufficient_sample(tmp_path):
    j = SqliteTradeJournal(tmp_path / "j.db")
    for i in range(25):                               # fills 5 bps au-dessus de la décision
        j.append(_trade(i, 100.0, 100.05), legacy=False)
    st = measured_slippage(j)
    assert st["available"] and st["n"] == 25
    assert abs(st["median_bps"] - 5.0) < 0.2 and abs(st["mean_bps"] - 5.0) < 0.2
    assert sabotage_cost_bps(j) == 10.0               # P90≈5 bps < plancher 10 → plancher


def test_trades_without_decision_price_ignored(tmp_path):
    j = SqliteTradeJournal(tmp_path / "j.db")
    t = _trade(0, 100.0, 100.0)
    t.features_snapshot = {}                          # pas de decision_price → exclu, pas 0 inventé
    j.append(t, legacy=False)
    assert measured_slippage(j)["n"] == 0
