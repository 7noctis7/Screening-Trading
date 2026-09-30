"""`make meta-smc` : le chemin complet s'exécute et consigne UN essai au registre."""

from __future__ import annotations

import importlib
import json
import sys

lab = importlib.import_module("scripts.meta_smc_lab")


def test_passage_complet(tmp_path, monkeypatch):
    from tests.ml.test_meta_smc import _marche
    replay = importlib.import_module("scripts.preset_replay")
    univers = {f"S{k}": _marche(n=500, graine=k, sym=f"S{k}") for k in range(6)}
    monkeypatch.setattr(replay, "_donnees", lambda: (univers, {}, "synthétique (test)"))
    monkeypatch.setenv("QUANT_ALLOW_SYNTHETIC", "1")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lab, "SORTIE", tmp_path / "meta.json")
    monkeypatch.setattr(sys, "argv", ["lab", "--modele", "logit", "--swing", "5"])
    assert lab.main() == 0
    rapport = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert rapport["filtre_utilisable"] is False                 # du bruit ne se filtre pas
    lignes = (tmp_path / "research" / "hypotheses.jsonl").read_text().splitlines()
    assert [json.loads(x)["facteur"] for x in lignes] == ["meta_smc:logit:5"]
