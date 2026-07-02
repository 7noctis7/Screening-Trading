"""Tests du journal persistant SQLite — round-trip, idempotence, JSON, contrat features."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest

from packages.core.models import (
    AssetClass, Bar, Side, Signal, SignalDirection, TradeRecord,
)
from packages.execution import CostModel, LiveTradingEngine, SimBroker
from packages.risk import RiskEngine
from packages.storage import SqliteTradeJournal


def _record(rid="L0001", features=None, **kw) -> TradeRecord:
    base = dict(
        id=rid, instrument="AAPL", asset_class=AssetClass.EQUITY, venue="alpaca",
        side=Side.LONG, qty=10.0, entry_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
        entry_price=150.0, avg_price=150.0, exit_ts=datetime(2026, 3, 2, tzinfo=timezone.utc),
        exit_price=160.0, pnl_net=100.0, pnl_pct=0.0666, r_multiple=2.0, is_win=True,
        mfe=12.0, mae=-3.0, features_snapshot=features if features is not None else {"rsi": 55.0})
    base.update(kw)
    return TradeRecord(**base)


def test_round_trip_identical():
    j = SqliteTradeJournal(":memory:")
    t = _record()
    j.append(t)
    (got,) = j.all()
    assert (got.id, got.instrument, got.asset_class, got.venue, got.side, got.qty) == (
        t.id, t.instrument, t.asset_class, t.venue, t.side, t.qty)
    assert got.entry_ts == t.entry_ts and got.exit_ts == t.exit_ts
    assert (got.entry_price, got.exit_price, got.pnl_net, got.r_multiple) == (
        t.entry_price, t.exit_price, t.pnl_net, t.r_multiple)
    assert got.is_win is True and got.mfe == 12.0 and got.mae == -3.0


def test_idempotence_same_id_single_row():
    j = SqliteTradeJournal(":memory:")
    j.append(_record(rid="X1", pnl_net=100.0))
    j.append(_record(rid="X1", pnl_net=999.0))          # même id, valeur différente
    rows = j.all()
    assert len(rows) == 1                                # une seule ligne
    assert rows[0].pnl_net == 999.0                      # UPSERT a mis à jour


def test_features_snapshot_json_round_trip():
    j = SqliteTradeJournal(":memory:")
    feats = {"rsi": 55.5, "atr": 2.34, "ref_price": 150.0, "conviction": 0.87, "sma": 148.2}
    j.append(_record(features=feats))
    assert j.all()[0].features_snapshot == feats         # dict non trivial préservé


def test_legacy_column_queryable():
    j = SqliteTradeJournal(":memory:")
    j.append(_record(rid="LIVE1", features={"rsi": 60.0}))
    j.append(_record(rid="LEG1", features={}), legacy=True)
    assert len(j.all()) == 2
    assert [r.id for r in j.all(legacy=False)] == ["LIVE1"]   # calibration : WHERE legacy=0
    assert [r.id for r in j.all(legacy=True)] == ["LEG1"]


def test_warns_on_empty_features_live(caplog):
    j = SqliteTradeJournal(":memory:")
    with caplog.at_level(logging.WARNING, logger="packages.storage.journal_sqlite"):
        j.append(_record(rid="NOFEAT", features={}))     # live SANS features → warning
    assert any("NOFEAT" in r.message and "features_snapshot" in r.message
               for r in caplog.records)


def test_no_warning_for_legacy_empty_features(caplog):
    j = SqliteTradeJournal(":memory:")
    with caplog.at_level(logging.WARNING, logger="packages.storage.journal_sqlite"):
        j.append(_record(rid="LEG", features={}), legacy=True)   # legacy → pas de warning
    assert caplog.records == []


# --------------------------------------------------------------------------- #
# Contrat anti-fuite : le snapshot journalisé == le dict connu À LA DÉCISION
# (ref_price inclus), aucune mutation/recompute entre décision et fill.
# --------------------------------------------------------------------------- #
class _OneShotStrategy:
    """Émet UN signal LONG à features connues, puis rien (le stop/target ferme)."""

    name = "contract"

    def __init__(self, features, stop, target):
        self._features = features
        self._stop = stop
        self._target = target
        self._emitted = False

    def generate_signals(self, bars, regime):
        if self._emitted or len(bars) < 3:
            return []
        self._emitted = True
        bar = bars[-1]
        return [Signal(bar.instrument, SignalDirection.LONG, self.name, bar.ts,
                       stop=self._stop, target=self._target,
                       features=dict(self._features), reason="entry")]


class _FixedSizer:
    def size(self, sig, equity, price, regime):
        return 10.0


def _bar(ts, close, high=None, low=None):
    return Bar("AAPL", "1d", ts, close, high or close, low or close, close, 1000.0)


def test_features_snapshot_matches_decision_no_recompute():
    decision_features = {"rsi": 60.0, "atr": 2.0}       # figées à la décision
    strat = _OneShotStrategy(decision_features, stop=95.0, target=110.0)
    j = SqliteTradeJournal(":memory:")
    eng = LiveTradingEngine(
        strategy=strat, sizer=_FixedSizer(), risk_engine=RiskEngine([]),
        broker=SimBroker(cash=100_000, costs=CostModel()), journal=j)

    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [
        _bar(t0.replace(day=1), 100.0),
        _bar(t0.replace(day=2), 100.0),
        _bar(t0.replace(day=3), 100.0),                 # len=3 → entrée LONG @ 100
        _bar(t0.replace(day=4), 105.0, high=111.0, low=104.0),  # high≥target → sortie @ 110
    ]
    for i in range(len(bars)):
        eng.step({"AAPL": bars[: i + 1]})

    (trade,) = j.all()
    # Le snapshot = features de décision + ref_price (prix connu à la décision), RIEN d'autre.
    assert trade.features_snapshot == {"rsi": 60.0, "atr": 2.0, "ref_price": 100.0}
    assert trade.features_snapshot["ref_price"] == 100.0   # prix d'entrée, pas un prix futur
    assert "rsi" in trade.features_snapshot and trade.features_snapshot["rsi"] == 60.0


def test_snapshot_immutable_after_persist():
    """Une fois persisté, muter le dict lu ne corrompt pas la base (isolation JSON)."""
    j = SqliteTradeJournal(":memory:")
    j.append(_record(features={"rsi": 55.0}))
    j.all()[0].features_snapshot["rsi"] = 999.0          # mutation d'une lecture
    assert j.all()[0].features_snapshot["rsi"] == 55.0   # base intacte
