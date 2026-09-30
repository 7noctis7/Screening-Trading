"""PR2 — guard pré-submit géométrie sleeve swing (TA#8).

Preset / strategy absente : guard inactive. strategy/sleeve=="swing" : exige
entry+stop+(target|rr)+setup_id+ts_decision avant _envoyer.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _hors_calendrier(monkeypatch):
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")


def _run_live():
    spec = importlib.util.spec_from_file_location("run_live", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Reponse:
    def __init__(self, status):
        self.status = status


class CourtierFactice:
    def __init__(self):
        self.ordres: list[tuple] = []

    def submit_notional(self, sym, side, montant):
        self.ordres.append((sym, montant))
        return _Reponse("accepted")

    def close_position(self, sym):
        self.ordres.append((sym, None))
        return True


def _preset(symbole, poids=0.05):
    return {"symbol": symbole, "broker_symbol": symbole, "weight_pct": poids,
            "capital": "alpaca", "asset_class": "equity", "tradeable": True}


def _swing_complete(symbole, poids=0.05, **extra):
    o = {"symbol": symbole, "broker_symbol": symbole, "weight_pct": poids,
         "capital": "alpaca", "asset_class": "equity", "tradeable": True,
         "strategy": "swing", "setup_id": "SFP",
         "entry": 100.0, "stop": 95.0, "target": 115.0, "rr": 3.0,
         "ts_decision": "2026-09-30T12:00:00+00:00", "risk_$": 50.0}
    o.update(extra)
    return o


def test_sleeve_geometry_missing_inactive_for_preset():
    rl = _run_live()
    assert rl.sleeve_geometry_missing(None) == []
    assert rl.sleeve_geometry_missing({}) == []
    assert rl.sleeve_geometry_missing(_preset("AAA")) == []
    assert rl.sleeve_geometry_missing({"strategy": "preset"}) == []


def test_sleeve_geometry_missing_lists_required_keys():
    rl = _run_live()
    miss = rl.sleeve_geometry_missing({"strategy": "swing"})
    assert set(miss) == {"entry", "stop", "target|rr", "setup_id", "ts_decision"}
    # target OR rr suffit
    assert "target|rr" not in rl.sleeve_geometry_missing(
        {"strategy": "swing", "entry": 1.0, "stop": 0.5, "rr": 3.0,
         "setup_id": "OTE", "ts_decision": "2026-09-30T00:00:00Z"})
    assert "target|rr" not in rl.sleeve_geometry_missing(
        {"strategy": "swing", "entry": 1.0, "stop": 0.5, "target": 2.0,
         "setup_id": "OTE", "ts_decision": "2026-09-30T00:00:00Z"})
    # sleeve flag aussi
    assert rl.sleeve_geometry_missing(
        {"sleeve": "swing", "entry": 1.0, "stop": 0.5, "target": 2.0,
         "setup_id": "IPA", "ts_decision": "t"}) == []
    # Nan / str vide = manquant
    miss2 = rl.sleeve_geometry_missing(
        {"strategy": "swing", "entry": float("nan"), "stop": 1.0, "target": 2.0,
         "setup_id": "  ", "ts_decision": ""})
    assert "entry" in miss2 and "setup_id" in miss2 and "ts_decision" in miss2


def test_preset_path_still_opens(monkeypatch):
    """Régression : ordre sans strategy/géom → envoyé (guard inactive)."""
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "0.15")
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "0.90")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl, b = _run_live(), CourtierFactice()
    sent, opened, _ = rl._reconcile([_preset("AAA", 0.10)],
                                    [("Alpaca", b, 100_000.0, {})], 1.0, None, dry=False)
    assert sent == 1
    assert len(b.ordres) == 1
    assert len(opened) == 1
    assert "strategy" not in opened[0]  # preset n'invente pas


def test_swing_missing_geometry_rejects_before_send(monkeypatch):
    """strategy=swing sans géom → 0 ordre, reject_missing_geometry."""
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "0.15")
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "0.90")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl, b = _run_live(), CourtierFactice()
    bad = _swing_complete("AAA", 0.10)
    del bad["entry"]  # manque entry
    sent, opened, _ = rl._reconcile([bad],
                                    [("Alpaca", b, 100_000.0, {})], 1.0, None, dry=False)
    assert sent == 0
    assert b.ordres == []
    assert opened == []


def test_swing_complete_geometry_passes_guard(monkeypatch):
    """strategy=swing + clés TA#8 → ordre part ; opened copie géom + strategy."""
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "0.15")
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "0.90")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl, b = _run_live(), CourtierFactice()
    o = _swing_complete("AAA", 0.10)
    sent, opened, _ = rl._reconcile([o],
                                    [("Alpaca", b, 100_000.0, {})], 1.0, None, dry=False)
    assert sent == 1
    assert len(b.ordres) == 1
    assert len(opened) == 1
    op = opened[0]
    assert op["strategy"] == "swing"
    assert op["setup_id"] == "SFP"
    assert op["entry"] == 100.0
    assert op["stop"] == 95.0
    assert op["target"] == 115.0
    assert op["ts_decision"] == "2026-09-30T12:00:00+00:00"
