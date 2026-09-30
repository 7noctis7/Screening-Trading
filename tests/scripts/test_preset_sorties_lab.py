"""Banc `make preset-sorties` : la règle de décision est celle écrite AVANT la mesure.

ADR-0208 : ADOPTABLE seulement si ΔSharpe apparié ≥ 0 ET maxDD amélioré d'au moins
3 points ; tout le reste est REJETÉ. Ces tests empêchent qu'un critère soit assoupli
après avoir vu les chiffres.
"""

from __future__ import annotations

import importlib
import json
import sys

import pytest

lab = importlib.import_module("scripts.preset_sorties_lab")


def _res(delta, dd_sans, dd_avec, dispo=True):
    return {"delta": {"disponible": dispo, "delta": delta},
            "sans": {"stats": {"max_drawdown": dd_sans}},
            "avec": {"stats": {"max_drawdown": dd_avec}}}


@pytest.mark.parametrize("delta, dd_sans, dd_avec, attendu", [
    (0.05, -0.30, -0.26, "ADOPTABLE"),       # Sharpe ≥ 0 et DD +4 points
    (0.00, -0.30, -0.27, "ADOPTABLE"),       # bornes incluses
    (-0.01, -0.30, -0.20, "REJETÉ"),         # le DD ne rachète pas un Sharpe perdu
    (0.20, -0.30, -0.28, "REJETÉ"),          # +2 points de DD : insuffisant
])
def test_regle_pre_enregistree(delta, dd_sans, dd_avec, attendu):
    assert lab.verdict(_res(delta, dd_sans, dd_avec)).startswith(attendu)


def test_sans_delta_calculable_rien_n_est_decide():
    assert lab.verdict(_res(0.1, -0.3, -0.2, dispo=False)).startswith("INDÉTERMINÉ")


def test_passage_complet_consigne_chaque_mode(tmp_path, monkeypatch):
    from tests.backtest.test_preset_rejeu import _panel
    replay = importlib.import_module("scripts.preset_replay")
    monkeypatch.setattr(replay, "_donnees", lambda: (_panel(), {}, "synthétique (test)"))
    monkeypatch.setenv("QUANT_ALLOW_SYNTHETIC", "1")
    monkeypatch.setenv("QUANT_CORE_SPEC", "qqq:0")
    monkeypatch.chdir(tmp_path)                         # le registre du test, pas le vrai
    monkeypatch.setattr(lab, "SORTIE", tmp_path / "sorties.json")
    monkeypatch.setattr(sys, "argv", ["lab", "--mode", "atr", "--mode", "structure",
                                      "--pas", "20"])
    assert lab.main() == 0
    bilan = json.loads((tmp_path / "sorties.json").read_text(encoding="utf-8"))
    assert set(bilan["modes"]) == {"atr", "structure"}
    registre = (tmp_path / "research" / "hypotheses.jsonl").read_text().splitlines()
    assert {json.loads(x)["facteur"] for x in registre} == {"preset_sorties:atr",
                                                            "preset_sorties:structure"}
