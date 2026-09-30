"""`simuler_horizons` : la grille PRÉ-ENREGISTRÉE tourne de bout en bout et consigne un
essai par scénario ; un horizon plus long que l'historique reste sans chiffre."""

from __future__ import annotations

import importlib
import json
import math
import sys

sh = importlib.import_module("scripts.simuler_horizons")
bt = importlib.import_module("tests.scripts.test_smclxtp_backtest")


def test_grille_pre_enregistree_de_bout_en_bout(tmp_path, monkeypatch):
    fichiers = [str(bt._export_fmp(tmp_path / "e.json", "NVDA", graine=3)),
                str(bt._export_fmp(tmp_path / "c.json", "BTCUSD", crypto=True, graine=4))]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sh, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["sh", "--fmp", *fichiers, "--debut", "2019-09-01"])
    assert sh.main() == 0
    r = json.loads((tmp_path / "out" / "horizons_fmp_1d.json").read_text(encoding="utf-8"))
    assert r["empreinte"].startswith("73dd06226a20")              # la grille déposée
    assert len(r["lignes"]) == 2 * 120
    dix_ans = [li["horizons"]["10"] for li in r["lignes"]]
    assert all(h["n"] == 0 and (h["rend_annuel_median"] is None
                                or math.isnan(h["rend_annuel_median"])) for h in dix_ans)
    reg = [json.loads(x) for x in (tmp_path / "research" / "hypotheses.jsonl").read_text()
           .splitlines()]
    assert reg[-1]["n_essais"] == 240
