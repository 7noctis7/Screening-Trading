"""Arch A3 — Capital A union : proteger HOLD, liquider_hors_cible=False, load_swing_orders."""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

from packages.execution import swing_sleeve as ss
from packages.risk.ddm import MachineDDM, ReglesDDM
from packages.strategies.moteur_swing import RiskManager

RACINE = pathlib.Path(__file__).resolve().parents[2]


def _rl():
    spec = importlib.util.spec_from_file_location("run_live", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _cible(s, w):
    return {"symbol": s, "broker_symbol": s, "weight_pct": w, "capital": "alpaca",
            "asset_class": "equity", "tradeable": True}


def _long_sfp_prop(symbole: str = "AAA") -> dict:
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


def _det(props, contradiction=False):
    return {
        "statut": "SHADOW_UNCALIBRATED",
        "sfp": {},
        "continuation": {},
        "propositions": list(props),
        "contradiction": contradiction,
    }


# --- weight_pct fraction ---


def test_build_swing_orders_weight_pct_is_fraction(monkeypatch):
    """weight_pct ∈ (0, 1] = notionnel/denom — pas ×100 (run_live pleine = w*cap)."""

    def fake_detecter(self, symbole, barres_1d, i=None):
        return _det([_long_sfp_prop(symbole)])

    monkeypatch.setattr(
        "packages.strategies.moteur_swing.MarketStructureEngine.detecter",
        fake_detecter,
    )
    rm = RiskManager(MachineDDM(ReglesDDM(r_base=0.01)))
    orders = ss.build_swing_orders(
        {"AAA": [object()]},
        equity_sleeve=10_000.0,
        equity_nav=100_000.0,
        ts_decision="2026-09-30T12:00:00Z",
        risk=rm,
    )
    assert len(orders) == 1
    o = orders[0]
    assert abs(o["weight_pct"] - o["notionnel"] / 100_000.0) < 1e-9
    assert 0.0 < o["weight_pct"] <= 1.0
    # never a "percent" scale for this size (notionnel << 100×)
    assert o["weight_pct"] < 1.0 or o["notionnel"] >= 100_000.0


# --- load_swing_orders ---


def test_load_swing_orders_flag_off_empty(monkeypatch):
    monkeypatch.delenv("QUANT_SWING_PAPER", raising=False)
    snap = {"live": {"swing_orders": [{"symbol": "AAA", "notionnel": 1000}]}}
    assert ss.load_swing_orders(snap) == []


def test_load_swing_orders_flag_on_sets_strategy(monkeypatch):
    monkeypatch.setenv("QUANT_SWING_PAPER", "1")
    # Mécanique de la sleeve UNE FOIS le veto CRO levé (cf. execution/swing_garde).
    monkeypatch.setattr("packages.execution.swing_garde.SORTIE_BRANCHEE", True)
    snap = {"live": {"swing_orders": [
        {"symbol": "AAA", "broker_symbol": "AAA", "notionnel": 1000.0},
        {"symbol": "BBB", "strategy": "swing", "notionnel": 500.0},
    ]}}
    out = ss.load_swing_orders(snap)
    assert len(out) == 2
    assert all(o["strategy"] == "swing" for o in out)
    assert out[0]["symbol"] == "AAA"


def test_load_swing_orders_missing_live(monkeypatch):
    monkeypatch.setenv("QUANT_SWING_PAPER", "true")
    assert ss.load_swing_orders({}) == []
    assert ss.load_swing_orders({"live": {}}) == []
    assert ss.load_swing_orders({"live": {"swing_orders": None}}) == []


# --- _broker_targets proteger / liquider_hors_cible ---


def test_broker_targets_proteger_holds_not_liquidate():
    """Preset hors-cible : protégé → val=détenu (HOLD) ; non protégé → val=0."""
    rl = _rl()
    targets = [_cible("CORE", 0.50)]
    cur = {"CORE": 40_000.0, "SLEEVE": 5_000.0, "JUNK": 2_000.0}
    tgt, _ = rl._broker_targets(
        targets, "Alpaca", 100_000.0, 1.0, cur,
        proteger={"SLEEVE"}, liquider_hors_cible=True,
    )
    assert tgt["CORE"]["val"] == pytest.approx(50_000.0)
    assert tgt["SLEEVE"]["val"] == pytest.approx(5_000.0)  # HOLD
    assert tgt["JUNK"]["val"] == 0.0                       # liquidate


def test_broker_targets_proteger_empty_still_liquidates():
    """Sans proteger : comportement historique — hors-cible → val=0."""
    rl = _rl()
    tgt, _ = rl._broker_targets(
        [_cible("CORE", 0.50)], "Alpaca", 100_000.0, 1.0,
        {"CORE": 40_000.0, "OLD": 3_000.0},
        proteger=None, liquider_hors_cible=True,
    )
    assert tgt["OLD"]["val"] == 0.0
    assert "CORE" in tgt


def test_broker_targets_no_liquider_hors_cible_skips_extras():
    """Pass sleeve : n'ajoute aucune ligne hors-cible (pas de liquidation parasite)."""
    rl = _rl()
    targets = [_cible("SWING", 0.05)]
    cur = {"SWING": 1_000.0, "CORE": 40_000.0, "OTHER": 2_000.0}
    tgt, _ = rl._broker_targets(
        targets, "Alpaca", 100_000.0, 1.0, cur,
        liquider_hors_cible=False,
    )
    assert "SWING" in tgt
    assert "CORE" not in tgt
    assert "OTHER" not in tgt
    assert tgt["SWING"]["val"] == pytest.approx(5_000.0)


def test_broker_targets_default_kwargs_match_legacy():
    """Signature défaut = ancien comportement (liquider hors-cible, pas de protect)."""
    rl = _rl()
    cur = {"AAA": 1_000.0, "BBB": 2_000.0}
    tgt_old_style, band1 = rl._broker_targets([_cible("AAA", 0.10)], "Alpaca", 100_000.0, 1.0, cur)
    tgt_explicit, band2 = rl._broker_targets(
        [_cible("AAA", 0.10)], "Alpaca", 100_000.0, 1.0, cur,
        proteger=None, liquider_hors_cible=True,
    )
    assert tgt_old_style.keys() == tgt_explicit.keys()
    assert tgt_old_style["BBB"]["val"] == 0.0
    assert tgt_explicit["BBB"]["val"] == 0.0
    assert band1 == band2
