"""Une donnée absente de la source reste absente (NaN) — jamais un multiple inventé.

Jusqu'au 06/10, sous l'étiquette « réel » : SEC → marge brute = 40 % du CA, EBIT = 1,3 ×
résultat, fonds propres = 50 % du CA, FCF = 0 ; yfinance → EBIT = 85 % de l'EBITDA,
marge brute absente = 0, fonds propres = 50 % du CA, FCF absent = 0.
"""

import math

import pytest

from packages.fundamentals import sec_provider as sec
from packages.fundamentals import yfinance_provider as yfp


def _faits(**concepts):
    return {"us-gaap": {c: {"units": {"USD": [
        {"end": "2025-12-31", "val": v, "form": "10-K", "fp": "FY", "fy": 2025,
         "filed": "2026-02-15"}]}} for c, v in concepts.items()}}


def test_sec_ne_fabrique_ni_marge_ni_ebit_ni_fonds_propres(monkeypatch):
    monkeypatch.setattr(sec, "_cik_map", lambda: {"XYZ": "0000000001"})
    monkeypatch.setattr(sec, "_facts", lambda cik: _faits(Revenues=1000.0,
                                                          NetIncomeLoss=100.0))
    p = sec.SECFundamentalsProvider()
    monkeypatch.setattr(p, "_price_shares", lambda s: (10.0, 50.0))
    f = p.get("XYZ")
    assert f.revenue == 1000.0 and f.net_income == 100.0
    for champ in ("gross_profit", "ebit", "ebitda", "total_equity", "fcf",
                  "interest_expense"):
        assert math.isnan(getattr(f, champ)), f"{champ} inventé : {getattr(f, champ)}"


def test_yfinance_ne_fabrique_ni_ebit_ni_marge_ni_fcf(monkeypatch):
    info = {"currentPrice": 10.0, "totalRevenue": 1000.0, "netIncomeToCommon": 100.0,
            "ebitda": 200.0, "sharesOutstanding": 50.0}
    monkeypatch.setattr(yfp, "_cache_get", lambda s: info)
    f = yfp.YFinanceFundamentalsProvider().get("XYZ")
    assert f.ebitda == 200.0
    for champ in ("ebit", "gross_profit", "total_equity", "fcf", "interest_expense"):
        assert math.isnan(getattr(f, champ)), f"{champ} inventé : {getattr(f, champ)}"


def test_yfinance_garde_les_valeurs_reelles(monkeypatch):
    info = {"currentPrice": 10.0, "totalRevenue": 1000.0, "netIncomeToCommon": 100.0,
            "ebitda": 200.0, "ebit": 150.0, "grossMargins": 0.4,
            "totalStockholderEquity": 800.0, "freeCashflow": 90.0,
            "sharesOutstanding": 50.0}
    monkeypatch.setattr(yfp, "_cache_get", lambda s: info)
    f = yfp.YFinanceFundamentalsProvider().get("XYZ")
    assert (f.ebit, f.total_equity, f.fcf) == (150.0, 800.0, 90.0)
    assert f.gross_profit == pytest.approx(400.0)
