from datetime import UTC, datetime

import pytest

from apps.api.snapshot import _fundamentals_section
from packages.fundamentals.models import Financials

SYMS = ["AAPL", "MSFT", "NVDA", "JPM", "XOM"]
ACMAP = {s: "equity" for s in SYMS}
NOMS = {s: s for s in SYMS}
SECT = {s: "Tech" for s in SYMS}


def test_section_synthetic_seulement_en_demo_explicite(monkeypatch):
    monkeypatch.setenv("QUANT_FUND", "synthetic")
    r = _fundamentals_section(SYMS, ACMAP, NOMS, SECT)
    assert r["available"] and r["n"] == 5
    assert r["source"].startswith("synthétique (démo")
    assert all(row["rating"] in ("BUY", "HOLD", "SELL") for row in r["rows"])
    assert all(0 <= row["score"] <= 100 for row in r["rows"])
    scores = [row["score"] for row in r["rows"]]
    assert scores == sorted(scores, reverse=True)


def test_sans_source_reelle_la_section_est_indisponible(monkeypatch):
    """Plus de repli synthétique implicite (06/10) : un chiffre inventé n'est pas
    noté."""
    monkeypatch.delenv("QUANT_FUND", raising=False)
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    import packages.common.net as net
    monkeypatch.setattr(net, "online", lambda *a, **k: False)
    r = _fundamentals_section(SYMS, ACMAP, NOMS, SECT)
    assert r["available"] is False and "synthétique est retiré" in r["reason"]


def _fin(sym, fcf):
    return Financials(symbol=sym, as_of=datetime(2026, 1, 1, tzinfo=UTC), sector="Tech",
                      price=10.0, shares=100.0, revenue=1000.0, gross_profit=400.0,
                      ebit=150.0, ebitda=200.0, net_income=100.0, total_equity=800.0,
                      total_debt=100.0, cash=50.0, fcf=fcf)


def test_une_donnee_absente_n_a_pas_de_note(monkeypatch):
    monkeypatch.setenv("QUANT_FUND", "yf")
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    import packages.fundamentals.sec_provider as sec
    import packages.fundamentals.yfinance_provider as yfp
    monkeypatch.setattr(sec, "_cik_map", lambda: {})
    fcfs = {"AAPL": 90.0, "MSFT": 50.0, "NVDA": 120.0, "JPM": 70.0, "XOM": float("nan")}
    monkeypatch.setattr(yfp.YFinanceFundamentalsProvider, "get",
                        lambda self, s, as_of=None: _fin(s, fcfs[s]))
    r = _fundamentals_section(SYMS, ACMAP, NOMS, SECT)
    xom = next(row for row in r["rows"] if row["symbol"] == "XOM")
    assert xom["score"] is None and xom["rating"] == "n/d"
    assert xom["combined_score"] is None and r["rows"][-1]["symbol"] == "XOM"
    notes = [row["score"] for row in r["rows"] if row["score"] is not None]
    assert len(notes) == 4 and max(notes) == pytest.approx(100.0)


def test_no_equities():
    r = _fundamentals_section(["BTC/USDC"], {"BTC/USDC": "crypto"}, {}, {})
    assert r["available"] is False
