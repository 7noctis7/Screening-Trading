"""Crypto paper via Alpaca (ADR-0029) — bout-en-bout journalisation + sizing vol-target.

1) Un trade crypto passé par LiveTradingEngine atterrit dans journal.db (SQLite) avec
   `asset_class=CRYPTO`, le bon `venue`, et un `features_snapshot` non vide.
2) Le sizing vol-target « voit » la vol réelle de l'instrument : une vol crypto (élevée)
   réduit la taille par rapport à une vol actions (faible), et `realized_vol` reflète la série.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

from packages.core.models import AssetClass
from packages.execution import LiveTradingEngine
from packages.portfolio.sizing.vol_target import VolTarget, realized_vol
from packages.storage.journal_sqlite import SqliteTradeJournal


class _Sizer:
    def size(self, sig, equity, price, regime):
        return 0.5


class _Risk:
    def approve(self, *a, **k):
        return SimpleNamespace(approved=True)


class _FilledBroker:
    name = "alpaca-paper"

    def equity(self):
        return 100_000.0

    def positions(self):
        return []

    def submit(self, order):
        from packages.core.models import OrderStatus
        order.status = OrderStatus.FILLED
        return order


def _sig():
    return SimpleNamespace(features={"atr": 900.0, "mom": 0.4}, stop=90.0, target=110.0,
                           reason="crypto_breakout")


def _bar(close=100.0):
    return SimpleNamespace(close=close, ts=datetime(2026, 1, 2, tzinfo=timezone.utc))


def test_crypto_trade_lands_in_journal_with_features():
    journal = SqliteTradeJournal(":memory:")
    eng = LiveTradingEngine(strategy=SimpleNamespace(name="crypto_test"), sizer=_Sizer(),
                            risk_engine=_Risk(), broker=_FilledBroker(), journal=journal)
    eng._try_open("BTC/USD", _sig(), _bar(), regime=None)
    assert "BTC/USD" in eng._open                     # ouvert au fill
    eng._close("BTC/USD", 110.0, _bar(110.0).ts, "target_hit")

    rows = journal.all()
    assert len(rows) == 1
    rec = rows[0]
    assert rec.instrument == "BTC/USD"
    assert rec.asset_class is AssetClass.CRYPTO       # pas EQUITY en dur
    assert rec.venue == "alpaca-paper"
    assert rec.features_snapshot.get("atr") == 900.0  # features_snapshot bien persisté
    assert rec.features_snapshot                       # non vide


def test_vol_target_sees_crypto_volatility():
    sizer = VolTarget(target_annual_vol=0.15)
    price = 30_000.0
    equity = 100_000.0
    # vol crypto élevée (ATR large) vs vol actions faible (ATR étroit), même prix/capital.
    crypto_sig = SimpleNamespace(features={"atr": 2_400.0})   # ~8 %/jour
    equity_sig = SimpleNamespace(features={"atr": 300.0})     # ~1 %/jour
    crypto_qty = sizer.size(crypto_sig, equity, price)
    equity_qty = sizer.size(equity_sig, equity, price)
    assert crypto_qty > 0 and equity_qty > 0
    assert crypto_qty < equity_qty                     # plus de vol → position plus petite


def test_realized_vol_reflects_series():
    calm = pd.Series([100 * (1.001 ** i) for i in range(40)])          # dérive douce
    wild = pd.Series([100 * (1.08 if i % 2 else 0.93) ** 1 for i in range(40)])  # swings crypto
    assert realized_vol(wild) > realized_vol(calm)
