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

# Preset-only symbol (BBY) : absent du screener, score via screen OU target_orders.
_SNAP_UNION = {
    "screener": {"rows": [
        {"symbol": "NVDA", "score": 1.23, "factors": {"momentum": 0.8}},
    ]},
    "screen": {"rows": [
        {"symbol": "HIMS", "score": 0.55},
        {"symbol": "NVDA", "score": 9.99},   # ne doit PAS écraser screener
    ]},
    "live": {"target_orders": [
        {"symbol": "BBY", "weight_pct": 0.04, "rank_score": 0.31},
        {"symbol": "NEM", "weight_pct": 0.02},          # pas de score → omis
        {"symbol": "BAD", "weight_pct": 0.01, "rank_score": None},  # None → omis
    ]},
    "dashboard": {"regime": {"cycle": "expansion", "risk_mode": "risk_on",
                             "exposure_multiplier": 1.0}},
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

def test_feature_map_unions_screen_and_target_orders():
    """rank_score depuis screener OU screen OU target_orders ; jamais de clé None."""
    fm = feature_map(_SNAP_UNION)
    assert fm["NVDA"]["rank_score"] == 1.23          # screener gagne sur screen
    assert fm["NVDA"]["momentum"] == 0.8
    assert fm["HIMS"]["rank_score"] == 0.55          # screen comble le trou
    assert fm["BBY"]["rank_score"] == 0.31           # target_orders (preset)
    assert "NEM" not in fm or "rank_score" not in fm.get("NEM", {})
    assert "BAD" not in fm or "rank_score" not in fm.get("BAD", {})


def test_build_open_keeps_float_rank_score_drops_none():
    tr = build_open("BBY", venue="Alpaca", asset_class="equity",
                    fill={"avg_price": 80.0, "qty": 10.0},
                    features={"rank_score": 0.31, "decision_price": 79.5,
                              "notionnel": 795.0, "ts_decision": "2026-09-30T12:00:00+00:00",
                              "note": "x", "bad": None},
                    regime=None, ts=TS)
    assert tr is not None
    assert tr.features_snapshot["rank_score"] == 0.31
    assert tr.features_snapshot["decision_price"] == 79.5
    assert tr.features_snapshot["notionnel"] == 795.0
    # exceptions str documentées : ts_decision (+ setup_id en PR1)
    assert tr.features_snapshot["ts_decision"] == "2026-09-30T12:00:00+00:00"
    assert "note" not in tr.features_snapshot and "bad" not in tr.features_snapshot


def test_build_open_omits_gain_attendu_unless_wired():
    """Sans expectancy_R×risk_$ : pas de gain_attendu (jamais ASSUMED_EDGE / PnL)."""
    tr = build_open("NVDA", venue="Alpaca", asset_class="equity",
                    fill={"avg_price": 120.0, "qty": 4.0},
                    features={"rank_score": 1.23, "decision_price": 119.0,
                              "notionnel": 476.0},
                    ts=TS)
    assert tr is not None
    assert "gain_attendu" not in tr.features_snapshot
    assert "expectancy_R" not in tr.features_snapshot

    tr2 = build_open("NVDA", venue="Alpaca", asset_class="equity",
                     fill={"avg_price": 120.0, "qty": 4.0},
                     features={"expectancy_R": 0.25, "risk_$": 40.0,
                               "gain_attendu": 10.0},  # caller a déjà calculé E_R×risk
                     ts=TS)
    assert tr2.features_snapshot["gain_attendu"] == 10.0
    assert tr2.features_snapshot["expectancy_R"] == 0.25


def test_journal_opens_propagates_strategy_swing():
    """PR1 : strategy sur opens[] → TradeRecord.strategy (plus le défaut hardcodé)."""
    jrn = SqliteTradeJournal(":memory:")
    opens = [
        {"symbol": "NVDA", "venue": "Alpaca", "asset_class": "equity",
         "fill": {"avg_price": 120.0, "qty": 4.0},
         "features": {"momentum": 0.8}, "regime": None, "strategy": "swing"},
    ]
    n = journal_opens(jrn, opens, ts=TS)
    assert n == 1
    live = jrn.all(legacy=False)
    assert live[0].strategy == "swing"


def test_journal_opens_default_strategy_preset():
    """Sans clé strategy (ou vide) → défaut preset — path inchangé."""
    jrn = SqliteTradeJournal(":memory:")
    opens = [
        {"symbol": "NVDA", "venue": "Alpaca", "asset_class": "equity",
         "fill": {"avg_price": 120.0, "qty": 4.0},
         "features": {"momentum": 0.8}, "regime": None},
        {"symbol": "BBY", "venue": "Alpaca", "asset_class": "equity",
         "fill": {"avg_price": 80.0, "qty": 2.0},
         "features": {}, "regime": None, "strategy": ""},
    ]
    journal_opens(jrn, opens, ts=TS)
    live = {t.instrument: t for t in jrn.all(legacy=False)}
    assert live["NVDA"].strategy == "preset"
    assert live["BBY"].strategy == "preset"


def test_build_open_keeps_entry_stop_target_and_setup_id():
    """PR1 : floats entry/stop/target + setup_id str survivent dans features_snapshot."""
    tr = build_open("NVDA", venue="Alpaca", asset_class="equity",
                    fill={"avg_price": 120.0, "qty": 4.0},
                    features={"entry": 119.5, "stop": 110.0, "target": 150.0,
                              "setup_id": "SFP", "rr": 3.2,
                              "ts_decision": "2026-09-30T12:00:00+00:00",
                              "note": "drop-me"},
                    strategy="swing", ts=TS)
    assert tr is not None
    assert tr.strategy == "swing"
    fs = tr.features_snapshot
    assert fs["entry"] == 119.5
    assert fs["stop"] == 110.0
    assert fs["target"] == 150.0
    assert fs["rr"] == 3.2
    assert fs["setup_id"] == "SFP"
    assert fs["ts_decision"] == "2026-09-30T12:00:00+00:00"
    assert "note" not in fs


def test_build_open_omits_empty_setup_id_and_no_invented_gain():
    """setup_id vide omis ; pas de gain_attendu inventé sans expectancy_R×risk_$. """
    tr = build_open("NVDA", venue="Alpaca", asset_class="equity",
                    fill={"avg_price": 120.0, "qty": 4.0},
                    features={"entry": 119.5, "stop": 110.0, "setup_id": "  ",
                              "risk_$": 40.0},  # risk seul → pas de gain_attendu
                    strategy="swing", ts=TS)
    assert tr is not None
    assert "setup_id" not in tr.features_snapshot
    assert "gain_attendu" not in tr.features_snapshot
    assert "expectancy_R" not in tr.features_snapshot
    assert tr.features_snapshot["entry"] == 119.5
    assert tr.features_snapshot["risk_$"] == 40.0
