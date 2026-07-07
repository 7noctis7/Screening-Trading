"""Mode léger d'exécution (QUANT_LIVE_LITE) : les sections coûteuses sont coupées, mais
uniquement quand le flag est actif, et jamais les sections essentielles au live."""
import os

from packages.common.safe_section import safe_section


def _boom():
    raise RuntimeError("ne doit pas être appelé en lite")


def _ok():
    return {"available": True, "value": 42}


def test_lite_skips_heavy_section(monkeypatch):
    monkeypatch.setenv("QUANT_LIVE_LITE", "1")
    r = safe_section("fundamentals", _boom)          # _boom PAS appelé → court-circuit
    assert r == {"available": False, "section": "fundamentals", "skipped": "live-lite"}


def test_lite_keeps_essential_section(monkeypatch):
    monkeypatch.setenv("QUANT_LIVE_LITE", "1")
    assert safe_section("screen", _ok)["value"] == 42       # screen = essentiel → exécuté
    assert safe_section("live", _ok)["value"] == 42


def test_no_lite_runs_everything(monkeypatch):
    monkeypatch.delenv("QUANT_LIVE_LITE", raising=False)
    assert safe_section("fundamentals", _ok)["value"] == 42  # sans flag → exécuté normalement
