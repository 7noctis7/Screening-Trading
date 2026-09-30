"""Arch A1 — sleeve swing paper : flag, producteur, rejects, cap."""

from __future__ import annotations

import math

import pytest

from packages.execution import swing_sleeve as ss
from packages.risk.ddm import MachineDDM, ReglesDDM
from packages.strategies.moteur_swing import RiskManager


def _long_sfp_prop(symbole: str = "AAA") -> dict:
    """Proposition long SFP géométriquement valide (rr=3)."""
    return {
        "statut": "SHADOW_UNCALIBRATED",
        "symbole": symbole,
        "scenario": "SFP",
        "sens": "long",
        "entree": 100.0,
        "stop": 96.0,
        "cible": 112.0,
        "rr": 3.0,
        "motifs": {},
    }


def _short_sfp_prop(symbole: str = "BBB") -> dict:
    return {
        "statut": "SHADOW_UNCALIBRATED",
        "symbole": symbole,
        "scenario": "SFP",
        "sens": "short",
        "entree": 100.0,
        "stop": 104.0,
        "cible": 88.0,
        "rr": 3.0,
        "motifs": {},
    }


def _det(props, contradiction=False):
    return {
        "statut": "SHADOW_UNCALIBRATED",
        "sfp": {},
        "continuation": {},
        "propositions": list(props),
        "contradiction": contradiction,
    }


def test_flag_default_off(monkeypatch):
    monkeypatch.delenv("QUANT_SWING_PAPER", raising=False)
    assert ss.swing_paper_enabled() is False
    monkeypatch.setenv("QUANT_SWING_PAPER", "0")
    assert ss.swing_paper_enabled() is False
    monkeypatch.setenv("QUANT_SWING_PAPER", "false")
    assert ss.swing_paper_enabled() is False
    monkeypatch.setenv("QUANT_SWING_PAPER", "")
    assert ss.swing_paper_enabled() is False


def test_flag_on_values(monkeypatch):
    for v in ("1", "true", "TRUE", "Yes", "yes", "True"):
        monkeypatch.setenv("QUANT_SWING_PAPER", v)
        assert ss.swing_paper_enabled() is True, v


def test_empty_bars_returns_empty():
    assert ss.build_swing_orders({}, equity_sleeve=100_000.0, ts_decision="2026-09-30T12:00:00Z") == []
    assert ss.build_swing_orders(None, equity_sleeve=100_000.0, ts_decision="2026-09-30T12:00:00Z") == []


def test_builds_long_sfp_or_ote_when_forced(monkeypatch):
    prop = _long_sfp_prop("AAA")

    def fake_detecter(self, symbole, barres_1d, i=None):
        return _det([prop])

    monkeypatch.setattr(
        "packages.strategies.moteur_swing.MarketStructureEngine.detecter",
        fake_detecter,
    )
    rm = RiskManager(MachineDDM(ReglesDDM(r_base=0.01)))
    orders = ss.build_swing_orders(
        {"AAA": [object()]},
        equity_sleeve=100_000.0,
        ts_decision="2026-09-30T12:00:00+02:00",
        risk=rm,
        asset_class_by_sym={"AAA": "equity"},
    )
    assert len(orders) == 1
    o = orders[0]
    assert o["symbol"] == "AAA"
    assert o["strategy"] == "swing"
    assert o["setup_id"] == "SFP"
    assert o["side"] == "long"
    assert o["entry"] == 100.0
    assert o["stop"] == 96.0
    assert o["target"] == 112.0
    assert o["rr"] == 3.0
    assert o["ts_decision"] == "2026-09-30T12:00:00+02:00"
    assert o["qty"] > 0
    # risk_$ = qty × |E−S| = risque_devise (1 % × 100k = 1000 $)
    assert abs(o["risk_$"] - 1000.0) < 1e-6
    assert abs(o["notionnel"] - o["qty"] * 100.0) < 1e-6
    assert o["broker"] == "Alpaca"
    assert o["broker_symbol"] == "AAA"
    assert o["tradeable"] is True
    assert o["asset_class"] == "equity"
    assert "weight_pct" in o
    # weight_pct = fraction 0–1 (notionnel/denom), pas un pourcent ×100
    assert abs(o["weight_pct"] - o["notionnel"] / 100_000.0) < 1e-9
    assert 0.0 < o["weight_pct"] <= 1.0


def test_skips_contradiction(monkeypatch):
    def fake_detecter(self, symbole, barres_1d, i=None):
        return _det([_long_sfp_prop(symbole)], contradiction=True)

    monkeypatch.setattr(
        "packages.strategies.moteur_swing.MarketStructureEngine.detecter",
        fake_detecter,
    )
    orders = ss.build_swing_orders(
        {"AAA": [object()]},
        equity_sleeve=100_000.0,
        ts_decision="2026-09-30T00:00:00Z",
    )
    assert orders == []


def test_long_only_skips_short(monkeypatch):
    def fake_detecter(self, symbole, barres_1d, i=None):
        return _det([_short_sfp_prop(symbole)])

    monkeypatch.setattr(
        "packages.strategies.moteur_swing.MarketStructureEngine.detecter",
        fake_detecter,
    )
    orders = ss.build_swing_orders(
        {"BBB": [object()]},
        equity_sleeve=100_000.0,
        ts_decision="2026-09-30T00:00:00Z",
        long_only=True,
    )
    assert orders == []


def test_max_names_cap(monkeypatch):
    def fake_detecter(self, symbole, barres_1d, i=None):
        return _det([_long_sfp_prop(symbole)])

    monkeypatch.setattr(
        "packages.strategies.moteur_swing.MarketStructureEngine.detecter",
        fake_detecter,
    )
    bars = {s: [object()] for s in ("ZZZ", "AAA", "MMM", "BBB", "CCC", "DDD")}
    orders = ss.build_swing_orders(
        bars,
        equity_sleeve=100_000.0,
        ts_decision="2026-09-30T00:00:00Z",
        max_names=3,
    )
    assert len(orders) == 3
    # ordre stable : symboles triés
    assert [o["symbol"] for o in orders] == ["AAA", "BBB", "CCC"]


def test_missing_ts_decision_yields_empty(monkeypatch):
    def fake_detecter(self, symbole, barres_1d, i=None):
        return _det([_long_sfp_prop(symbole)])

    monkeypatch.setattr(
        "packages.strategies.moteur_swing.MarketStructureEngine.detecter",
        fake_detecter,
    )
    assert ss.build_swing_orders(
        {"AAA": [object()]},
        equity_sleeve=100_000.0,
        ts_decision="",
    ) == []


def test_no_expectancy_keys_invented(monkeypatch):
    def fake_detecter(self, symbole, barres_1d, i=None):
        return _det([_long_sfp_prop(symbole)])

    monkeypatch.setattr(
        "packages.strategies.moteur_swing.MarketStructureEngine.detecter",
        fake_detecter,
    )
    orders = ss.build_swing_orders(
        {"AAA": [object()]},
        equity_sleeve=50_000.0,
        ts_decision="2026-09-30T00:00:00Z",
    )
    assert len(orders) == 1
    o = orders[0]
    for k in ("p_calibrated", "expectancy_R", "gain_attendu", "accept"):
        assert k not in o
    assert math.isfinite(o["rr"]) and math.isfinite(o["risk_$"])


# --- Arch A2 : attach_swing_orders / env helpers ---


def test_swing_nav_pct_default_and_fraction(monkeypatch):
    monkeypatch.delenv("QUANT_SWING_NAV_PCT", raising=False)
    assert ss.swing_nav_pct() == 0.0
    monkeypatch.setenv("QUANT_SWING_NAV_PCT", "0.05")
    assert abs(ss.swing_nav_pct() - 0.05) < 1e-12
    monkeypatch.setenv("QUANT_SWING_NAV_PCT", "2")  # clamp
    assert ss.swing_nav_pct() == 1.0
    monkeypatch.setenv("QUANT_SWING_NAV_PCT", "nope")
    assert ss.swing_nav_pct() == 0.0


def test_swing_max_names_default(monkeypatch):
    monkeypatch.delenv("QUANT_SWING_MAX_NAMES", raising=False)
    assert ss.swing_max_names() == 5
    monkeypatch.setenv("QUANT_SWING_MAX_NAMES", "3")
    assert ss.swing_max_names() == 3
    monkeypatch.setenv("QUANT_SWING_MAX_NAMES", "0")
    assert ss.swing_max_names() == 5
    monkeypatch.setenv("QUANT_SWING_MAX_NAMES", "x")
    assert ss.swing_max_names() == 5


def test_attach_flag_off_sets_empty(monkeypatch):
    monkeypatch.delenv("QUANT_SWING_PAPER", raising=False)
    live = {"target_orders": [{"symbol": "PRESET", "weight_pct": 10.0}]}
    preset_before = list(live["target_orders"])
    ss.attach_swing_orders(
        live,
        bars_by_sym={"AAA": [object()]},
        equity_nav=100_000.0,
        ts_decision="2026-09-30T12:00:00Z",
    )
    assert live["swing_orders"] == []
    assert live["target_orders"] == preset_before


def test_attach_on_pct_zero_sets_empty(monkeypatch):
    monkeypatch.setenv("QUANT_SWING_PAPER", "1")
    monkeypatch.setenv("QUANT_SWING_NAV_PCT", "0")
    live = {"target_orders": [{"symbol": "PRESET", "weight_pct": 10.0}]}
    preset_before = [dict(o) for o in live["target_orders"]]
    ss.attach_swing_orders(
        live,
        bars_by_sym={"AAA": [object()]},
        equity_nav=100_000.0,
        ts_decision="2026-09-30T12:00:00Z",
    )
    assert live["swing_orders"] == []
    assert live["target_orders"] == preset_before


def test_attach_on_with_monkeypatched_build(monkeypatch):
    monkeypatch.setenv("QUANT_SWING_PAPER", "1")
    monkeypatch.setenv("QUANT_SWING_NAV_PCT", "0.10")
    monkeypatch.setenv("QUANT_SWING_MAX_NAMES", "5")
    fake_orders = [{
        "symbol": "AAA", "strategy": "swing", "setup_id": "SFP", "side": "long",
        "entry": 100.0, "stop": 96.0, "target": 112.0, "rr": 3.0,
        "ts_decision": "2026-09-30T12:00:00Z", "qty": 10.0, "notionnel": 1000.0,
        "risk_$": 40.0, "broker": "Alpaca", "broker_symbol": "AAA", "tradeable": True,
    }]

    def fake_build(bars_by_sym, **kwargs):
        assert bars_by_sym == {"AAA": ["bar"]}
        assert abs(kwargs["equity_sleeve"] - 10_000.0) < 1e-9  # 10% of 100k
        assert kwargs["equity_nav"] == 100_000.0
        assert kwargs["ts_decision"] == "2026-09-30T12:00:00Z"
        assert kwargs["max_names"] == 5
        return list(fake_orders)

    monkeypatch.setattr(ss, "build_swing_orders", fake_build)
    live = {"target_orders": [{"symbol": "PRESET", "weight_pct": 10.0}]}
    preset_before = [dict(o) for o in live["target_orders"]]
    ss.attach_swing_orders(
        live,
        bars_by_sym={"AAA": ["bar"]},
        equity_nav=100_000.0,
        ts_decision="2026-09-30T12:00:00Z",
        rank_scores={"AAA": 0.87},
    )
    assert len(live["swing_orders"]) == 1
    assert live["swing_orders"][0]["symbol"] == "AAA"
    assert live["swing_orders"][0]["strategy"] == "swing"
    assert live["swing_orders"][0]["rank_score"] == 0.87
    assert live["target_orders"] == preset_before
    for k in ("p_calibrated", "expectancy_R", "gain_attendu"):
        assert k not in live["swing_orders"][0]


def test_swing_bars_by_sym_filters():
    data = {"AAA": [1, 2], "BBB": [], "CCC": [3]}
    assert ss.swing_bars_by_sym(["AAA", "BBB", "CCC", "DDD", ""], data) == {
        "AAA": [1, 2],
        "CCC": [3],
    }
    assert ss.swing_bars_by_sym([], data) == {}
    assert ss.swing_bars_by_sym(["AAA"], None) == {}
