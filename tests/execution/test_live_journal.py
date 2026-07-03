"""Journalisation des ouvertures de réconciliation paper (P0-4) — `legacy=0` + features de décision.

Contrat vérifié (anti look-ahead, cf. garde-fou CLAUDE.md) :
  - les FEATURES proviennent UNIQUEMENT du snapshot de décision (jamais reconstruites) ;
  - les FAITS d'exécution (prix/qté) viennent du fill broker ; fill inexploitable → rien journalisé ;
  - `id` déterministe par (jour, broker, symbole) → re-run du même jour = idempotent (UPSERT).
"""
from __future__ import annotations

from datetime import datetime, timezone

from packages.core.models import AssetClass, Side
from packages.execution.live_journal import (build_open, feature_map, journal_opens,
                                             regime_context)
from packages.storage import SqliteTradeJournal

TS = datetime(2026, 7, 6, 16, 5, tzinfo=timezone.utc)

_SNAP = {
    "screener": {"rows": [
        {"symbol": "NVDA", "score": 1.23, "factors": {"momentum": 0.8, "value": -0.2}},
        {"symbol": "BTC/USD", "score": 0.4, "factors": {"trend": 0.5}},
    ]},
    "dashboard": {"regime": {"cycle": "expansion", "risk_mode": "risk_on",
                             "exposure_multiplier": 1.1}},
}


def test_feature_map_from_screener():
    fm = feature_map(_SNAP)
    assert fm["NVDA"] == {"rank_score": 1.23, "momentum": 0.8, "value": -0.2}
    assert fm["BTC/USD"]["trend"] == 0.5


def test_regime_context_label_and_expo():
    label, ctx = regime_context(_SNAP)
    assert label == "expansion/risk_on"
    assert ctx == {"regime_expo": 1.1}


def test_build_open_valid_fill_captures_decision_features():
    tr = build_open("NVDA", venue="Alpaca", asset_class="equity",
                    fill={"avg_price": 120.0, "qty": 4.0},
                    features={"momentum": 0.8, "flag": True, "bad": float("nan"), "note": "x"},
                    regime="expansion/risk_on", ts=TS)
    assert tr is not None
    assert tr.id == "P-20260706-Alpaca-NVDA"          # déterministe → idempotent
    assert tr.asset_class is AssetClass.EQUITY and tr.side is Side.LONG
    assert tr.entry_price == 120.0 and tr.qty == 4.0 and tr.avg_price == 120.0
    assert tr.regime == "expansion/risk_on"
    # features_snapshot = floats finis uniquement (bool/NaN/str exclus → JSON/ML-safe)
    assert tr.features_snapshot == {"momentum": 0.8}


def test_build_open_infers_crypto_from_symbol():
    tr = build_open("BTC/USD", venue="Alpaca", asset_class=None,
                    fill={"avg_price": 60000.0, "qty": 0.01}, features={"trend": 0.5}, ts=TS)
    assert tr is not None and tr.asset_class is AssetClass.CRYPTO


def test_build_open_none_on_unusable_fill():
    for fill in ({"avg_price": 0.0, "qty": 4.0}, {"avg_price": 120.0, "qty": 0.0}, None):
        assert build_open("NVDA", venue="Alpaca", asset_class="equity",
                          fill=fill, features={"momentum": 0.8}, ts=TS) is None


def test_journal_opens_writes_legacy0_and_skips_bad_fills():
    jrn = SqliteTradeJournal(":memory:")
    opens = [
        {"symbol": "NVDA", "venue": "Alpaca", "asset_class": "equity",
         "fill": {"avg_price": 120.0, "qty": 4.0},
         "features": {"momentum": 0.8, "target_weight": 0.1}, "regime": "expansion/risk_on"},
        {"symbol": "BTC/USD", "venue": "Alpaca", "asset_class": "crypto",
         "fill": None, "features": {"trend": 0.5}, "regime": None},   # pas de fill → skip
    ]
    n = journal_opens(jrn, opens, ts=TS)
    assert n == 1
    live = jrn.all(legacy=False)
    assert len(live) == 1 and live[0].instrument == "NVDA"
    assert live[0].features_snapshot == {"momentum": 0.8, "target_weight": 0.1}


def test_journal_opens_idempotent_same_day():
    jrn = SqliteTradeJournal(":memory:")
    op = [{"symbol": "NVDA", "venue": "Alpaca", "asset_class": "equity",
           "fill": {"avg_price": 120.0, "qty": 4.0}, "features": {"momentum": 0.8}, "regime": None}]
    journal_opens(jrn, op, ts=TS)
    journal_opens(jrn, op, ts=TS)                     # 2e run même jour → UPSERT, pas de doublon
    assert len(jrn.all(legacy=False)) == 1
