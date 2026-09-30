"""`smclxtp_backtest` : les deux sources (export FMP, Yahoo) donnent la même série, et le
passage complet consigne un essai et ses KPI."""

from __future__ import annotations

import importlib
import json
import sys

import numpy as np
import pandas as pd

bt = importlib.import_module("scripts.smclxtp_backtest")


def _prix(n=700, graine=0):
    rng = np.random.default_rng(graine)
    c = 50 * np.exp(np.cumsum(rng.normal(0.0005, 0.025, n)))
    jours = pd.bdate_range("2019-06-03", periods=n)
    return jours, c * (1 + rng.normal(0, 0.004, n)), c * 1.012, c * 0.988, c


def _export_fmp(chemin, symbole, crypto=False, graine=0):
    jours, o, h, lo, c = _prix(graine=graine)
    if crypto:
        lignes = [{"symbol": symbole, "date": d.strftime("%Y-%m-%d"), "open": a, "high": b,
                   "low": x, "close": y, "volume": 1.0} for d, a, b, x, y in zip(jours, o, h, lo, c, strict=True)]
    else:
        lignes = [{"symbol": symbole, "date": d.strftime("%Y-%m-%d"), "adjOpen": a,
                   "adjHigh": b, "adjLow": x, "adjClose": y, "volume": 1}
                  for d, a, b, x, y in zip(jours, o, h, lo, c, strict=True)]
    chemin.write_text(json.dumps(lignes[::-1]))          # FMP rend du plus récent au plus ancien
    return chemin


def test_export_fmp_trie_et_classe(tmp_path):
    s = bt.depuis_fmp(str(_export_fmp(tmp_path / "a.json", "NVDA")))
    assert s["jours"] == sorted(s["jours"]) and s["symbole"] == "NVDA"
    assert bt._classe("NVDA") == "equity" and bt._classe("BTCUSD") == "crypto"
    assert bt._classe("ETH-USD") == "crypto"


def test_yahoo_colonnes_multi_index(monkeypatch):
    jours, o, h, lo, c = _prix(n=50)
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], ["PL"]])
    df = pd.DataFrame(np.column_stack([o, h, lo, c, np.ones(50)]), index=jours, columns=cols)
    import yfinance
    monkeypatch.setattr(yfinance, "download", lambda *a, **k: df)
    s = bt.depuis_yahoo("PL")
    assert len(s["jours"]) == 50 and s["c"][-1] == c[-1]


def test_passage_complet(tmp_path, monkeypatch):
    fichiers = [str(_export_fmp(tmp_path / "e.json", "NVDA", graine=1)),
                str(_export_fmp(tmp_path / "c.json", "BTCUSD", crypto=True, graine=2))]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bt, "SORTIE", tmp_path / "bt.json")
    monkeypatch.setattr(sys, "argv", ["bt", "--fmp", *fichiers, "--swing", "10",
                                      "--pivot", "10", "--modele", "logit"])
    assert bt.main() == 0
    r = json.loads((tmp_path / "bt.json").read_text(encoding="utf-8"))
    assert [a["symbole"] for a in r["actifs"]] == ["NVDA", "BTCUSD"]
    assert r["actifs"][1]["cout_par_jambe"] > r["actifs"][0]["cout_par_jambe"]   # crypto
    for a in r["actifs"]:
        assert {"trades", "win_rate", "duree_moyenne_jours", "profit_factor", "max_drawdown",
                "sharpe", "sortino", "cagr", "pnl_moyen", "pnl_moyen_pct"} <= set(a)
    registre = (tmp_path / "research" / "hypotheses.jsonl").read_text().splitlines()
    assert json.loads(registre[0])["facteur"] == "smclxtp_backtest:10:10"
