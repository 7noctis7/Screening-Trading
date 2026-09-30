"""`comparer_strategies` : chemin complet sur exports FMP, et agrégation 1h → 1d."""

from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime, timedelta

from packages.core.models import Bar

cs = importlib.import_module("scripts.comparer_strategies")
bt = importlib.import_module("tests.scripts.test_smclxtp_backtest")


def test_agregation_horaire_en_journalier():
    d0 = datetime(2024, 1, 1, tzinfo=UTC)
    h = [Bar("X", "1h", d0 + timedelta(hours=k), 10 + k, 11 + k, 9 + k, 10.5 + k, 1.0)
         for k in range(48)]
    j = cs._journalier(h)
    assert len(j) == 2 and j[0].timeframe == "1d"
    assert (j[0].open, j[0].high, j[0].low, j[0].close) == (10, 11 + 23, 9, 10.5 + 23)
    assert j[1].volume == 24.0


def test_passage_complet_sur_exports(tmp_path, monkeypatch):
    fichiers = [str(bt._export_fmp(tmp_path / "e.json", "NVDA", graine=1)),
                str(bt._export_fmp(tmp_path / "c.json", "BTCUSD", crypto=True, graine=2))]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cs, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["cs", "--fmp", *fichiers, "--debut", "2019-09-01"])
    assert cs.main() == 0
    r = json.loads((tmp_path / "out" / "comparaison_fmp_1d.json").read_text(encoding="utf-8"))
    assert set(r["synthese"]) == {"smclxtp", "ma_crossover", "rsi_reversion", "swing",
                                  "buy_and_hold"}
    reg = [json.loads(x) for x in (tmp_path / "research" / "hypotheses.jsonl").read_text()
           .splitlines()]
    assert reg[0]["n_essais"] == 4 * 2
