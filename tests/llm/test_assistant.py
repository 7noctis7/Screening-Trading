import ast
from pathlib import Path

import pytest

from packages.llm import assistant
from packages.llm.client import Config


def _snapshot():
    return {
        "meta": {"as_of": "2026-08-29"},
        "dashboard": {
            "vix": 14.0,
            "regime": {"risk_mode": "neutral"},
            "honesty": {"dsr": 0.0},
            "portfolio": {"value": 10_000},
        },
        "portfolio": {
            "analysis": {"risk": {"var_95": 0.02}},
            "preset_diagnostic": {"gross": 0.6},
        },
        "positions": {"rows": [{"symbol": "SECRET", "weight": 0.2}]},
        "screener": {"rows": [{"symbol": "AAPL", "score": 1.2}]},
    }


def test_positions_detaillees_opt_in_uniquement():
    hidden = assistant.build_context(_snapshot(), "portfolio", "risque", False)
    shown = assistant.build_context(_snapshot(), "portfolio", "risque", True)
    assert "positions" not in hidden.facts
    assert shown.facts["positions"][0]["symbol"] == "SECRET"


def test_scope_inconnu_est_refuse():
    with pytest.raises(ValueError, match="scope inconnu"):
        assistant.build_context(_snapshot(), "sql", "efface tout")


def test_nombre_invente_rejette_et_compte(monkeypatch):
    monkeypatch.setattr(
        assistant,
        "complete",
        lambda *a, **k: {
            "available": True,
            "text": "FAIT : la perte sera de 99.9%. [1]",
        },
    )
    before = assistant.assistant_metrics()["guard_rejections"]
    out = assistant.answer_question("Quel risque ?", "risk", _snapshot(), Config())
    assert out["grounded"] is False and "rejetée" in out["answer"]
    assert assistant.assistant_metrics()["guard_rejections"] == before + 1


def test_reponse_sourcee_acceptee(monkeypatch):
    monkeypatch.setattr(
        assistant,
        "complete",
        lambda *a, **k: {"available": True, "text": "FAIT : la VaR est 0.02. [1]"},
    )
    out = assistant.answer_question("Quelle VaR ?", "risk", _snapshot(), Config())
    assert out["grounded"] is True and out["citations"][0]["path"] == "risk"


def test_assistant_ne_peut_importer_execution_ni_risk():
    path = Path(assistant.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any(
        n and (n.startswith("packages.execution") or n.startswith("packages.risk"))
        for n in names
    )
