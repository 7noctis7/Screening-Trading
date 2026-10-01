"""Arch/QT PR4 — protect multi-jour : journal strategy=swing ∪ snap, preset HOLD."""

from __future__ import annotations

import importlib.util
import pathlib
from datetime import datetime, timezone

import pytest

from packages.core.models import AssetClass, Side, TradeRecord
from packages.execution import swing_sleeve as ss
from packages.storage.journal_sqlite import SqliteTradeJournal

RACINE = pathlib.Path(__file__).resolve().parents[2]


def _rl():
    spec = importlib.util.spec_from_file_location("run_live", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _cible(s, w):
    return {"symbol": s, "broker_symbol": s, "weight_pct": w, "capital": "alpaca",
            "asset_class": "equity", "tradeable": True}


def _lot(
    id: str,
    sym: str = "AAA",
    *,
    strategy: str | None = "swing",
    exit_ts: datetime | None = None,
    qty: float = 10.0,
) -> TradeRecord:
    return TradeRecord(
        id=id,
        instrument=sym,
        asset_class=AssetClass.EQUITY,
        venue="Alpaca",
        side=Side.LONG,
        qty=qty,
        entry_ts=datetime(2026, 9, 28, tzinfo=timezone.utc),
        entry_price=100.0,
        avg_price=100.0,
        exit_ts=exit_ts,
        exit_price=110.0 if exit_ts is not None else None,
        strategy=strategy,
        entry_reason="test",
        features_snapshot={},
    )


# --- sleeve_open_symbols ---


def test_sleeve_open_symbols_only_open_robot_swing():
    """Open robot swing → inclus ; fermé / preset / non-robot → exclus."""
    j = SqliteTradeJournal(":memory:")
    j.append(_lot("P-20260928-Alpaca-SWG", "SWG", strategy="swing"), legacy=False)
    j.append(_lot("C-SWG2-aabbcc", "SWG2", strategy="swing"), legacy=False)
    j.append(_lot("R-20260928-Alpaca-SWG3-1", "SWG3", strategy="swing"), legacy=False)
    # fermé swing
    j.append(
        _lot(
            "P-20260920-Alpaca-OLD",
            "OLD",
            strategy="swing",
            exit_ts=datetime(2026, 9, 25, tzinfo=timezone.utc),
        ),
        legacy=False,
    )
    # open preset
    j.append(_lot("P-20260928-Alpaca-PRE", "PRE", strategy="preset"), legacy=False)
    # open sans strategy
    j.append(_lot("P-20260928-Alpaca-NOS", "NOS", strategy=None), legacy=False)
    # non-robot (LEG-)
    j.append(_lot("LEG-ad4ac9fa7f59", "LEG", strategy="swing"), legacy=True)
    # préfixe inconnu
    j.append(_lot("X-9000", "XXX", strategy="swing"), legacy=False)

    got = ss.sleeve_open_symbols(j)
    assert got == {"SWG", "SWG2", "SWG3"}


def test_sleeve_open_symbols_empty_journal():
    j = SqliteTradeJournal(":memory:")
    assert ss.sleeve_open_symbols(j) == set()


def test_sleeve_open_symbols_failure_returns_empty():
    """Best-effort : journal cassé → set() (pas de crash)."""

    class _Boom:
        def all(self):
            raise RuntimeError("db down")

    assert ss.sleeve_open_symbols(_Boom()) == set()


# --- merge_protect_symbols ---


def test_merge_protect_symbols_union_and_normalize():
    swing = [
        {"symbol": "aaa", "broker_symbol": "AAA"},
        {"symbol": "btc/usd", "broker_symbol": "BTC/USD"},
        {"symbol": "only-sym"},  # pas de broker_symbol
    ]
    journal = {"HOLD", "btc-usd", "AAA"}  # AAA déjà dans swing

    def _n(s):
        return (s or "").replace("/", "").replace("-", "").upper()

    got = ss.merge_protect_symbols(swing, journal, normalize=_n)
    assert got == {"AAA", "BTCUSD", "ONLYSYM", "HOLD"}


def test_merge_protect_symbols_empty_inputs():
    assert ss.merge_protect_symbols([], [], normalize=str) == set()
    assert ss.merge_protect_symbols(None, None, normalize=str) == set()
    assert ss.merge_protect_symbols(
        [{"symbol": "X"}], frozenset(), normalize=str,
    ) == {"X"}


# --- _broker_targets HOLD journal-only ---


def test_broker_targets_proteger_holds_journal_only_symbol():
    """Symbole journal-only dans proteger → HOLD (val=détenu), pas liquidation."""
    rl = _rl()
    targets = [_cible("CORE", 0.50)]
    cur = {"CORE": 40_000.0, "SWG": 5_000.0, "JUNK": 2_000.0}
    tgt, _ = rl._broker_targets(
        targets, "Alpaca", 100_000.0, 1.0, cur,
        proteger={"SWG"}, liquider_hors_cible=True,
    )
    assert tgt["CORE"]["val"] == pytest.approx(50_000.0)
    assert tgt["SWG"]["val"] == pytest.approx(5_000.0)  # HOLD journal
    assert tgt["JUNK"]["val"] == 0.0
