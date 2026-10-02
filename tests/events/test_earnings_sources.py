"""Calendrier de résultats : les SOURCES réseau et le tri (31 % de couverture au 02/10).

Ce calendrier alimente `_earnings_risk` (résultats imminents des positions détenues) et
les zones de résultats des graphiques. Ces tests épinglent, sans réseau :
  1. sans clé FMP, aucun appel FMP — repli yfinance ;
  2. une panne ou une réponse inattendue de FMP rend [] au lieu de planter ;
  3. un rapport À VENIR n'a jamais de BPA réel (pas de « surprise » fabriquée) ;
  4. seules les dates de la fenêtre [−days_back, +days_fwd] sont gardées ;
  5. revenu estimé → prochain rapport seulement ; revenu réel → dernier publié ;
  6. un titre en panne n'empêche pas les autres ; à venir d'abord, puis les récents.
"""

import io
import json
import sys
import types
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from packages.events import earnings as e

AUJ = datetime.now(UTC).date()


def _j(n: int):
    return AUJ + timedelta(days=n)


@pytest.fixture(autouse=True)
def _sans_cle(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)


def test_sans_cle_fmp_aucun_appel_reseau(monkeypatch):
    def interdit(*a, **k):
        raise AssertionError("FMP appelé sans clé")
    monkeypatch.setattr(e.urllib.request, "urlopen", interdit)
    assert e._fmp_earnings({"AAPL"}, 21, 120) == []


def _fmp_repond(monkeypatch, corps):
    vu = {}

    def urlopen(url, timeout):
        vu["url"] = url
        if isinstance(corps, Exception):
            raise corps
        return io.BytesIO(json.dumps(corps).encode())
    monkeypatch.setenv("FMP_API_KEY", "cle-test")
    monkeypatch.setattr(e.urllib.request, "urlopen", urlopen)
    return vu


def test_fmp_fenetre_dans_l_url_et_filtre_sur_les_symboles(monkeypatch):
    vu = _fmp_repond(monkeypatch, [
        {"symbol": "aapl", "date": _j(5).isoformat(), "eps": 1.2},
        {"symbol": "MSFT", "date": _j(6).isoformat()}])
    (r,) = e._fmp_earnings({"AAPL"}, 21, 120)
    assert r["symbol"] == "AAPL" and r["source"] == "FMP"
    assert f"from={_j(-21).isoformat()}&to={_j(120).isoformat()}" in vu["url"]


@pytest.mark.parametrize("corps", [ConnectionError("FMP muet"),
                                   {"Error Message": "plan limité"}])
def test_fmp_en_panne_ou_reponse_inattendue_rend_vide(monkeypatch, corps):
    _fmp_repond(monkeypatch, corps)
    assert e._fmp_earnings({"AAPL"}, 21, 120) == []


class Ticker:
    """`yf.Ticker` factice : dates de résultats, calendrier, comptes trimestriels."""
    pannes: set = set()

    def __init__(self, sym):
        if sym in self.pannes:
            raise ConnectionError(f"{sym} injoignable")
        self.sym = sym
        self.calendar = {"Earnings Date": [_j(10)], "Revenue Average": 5e9}
        self.quarterly_income_stmt = pd.DataFrame(
            {pd.Timestamp(_j(-40)): [4.8e9]}, index=["Total Revenue"])

    def get_earnings_dates(self, limit=12):
        jours = [10, 40, -7, -60, 400]                  # 40 : hors fenêtre de 30 j
        idx = pd.DatetimeIndex([pd.Timestamp(_j(n)) for n in jours])
        return pd.DataFrame({"EPS Estimate": [1.0, 1.1, 0.9, 0.8, 1.5],
                             "Reported EPS": [9.9, 9.9, 0.95, 0.7, 9.9]}, index=idx)


@pytest.fixture
def yf(monkeypatch):
    Ticker.pannes = set()
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Ticker))
    return Ticker


def test_yfinance_un_rapport_a_venir_n_a_pas_de_bpa_reel(yf):
    rows = {r["date"]: r for r in e._yf_earnings(["aapl"], days_back=21, days_fwd=30)}
    assert set(rows) == {_j(10).isoformat(), _j(-7).isoformat()}     # fenêtre respectée
    a_venir, publie = rows[_j(10).isoformat()], rows[_j(-7).isoformat()]
    assert a_venir["eps_actual"] is None and a_venir["eps_estimate"] == 1.0
    assert publie["eps_actual"] == 0.95 and publie["symbol"] == "AAPL"


def test_yfinance_revenus_rattaches_au_bon_trimestre(yf):
    rows = {r["date"]: r for r in e._yf_earnings(["AAPL"], days_back=21, days_fwd=30)}
    a_venir, publie = rows[_j(10).isoformat()], rows[_j(-7).isoformat()]
    assert a_venir["revenue_estimate"] == 5e9 and a_venir["revenue_actual"] is None
    assert publie["revenue_actual"] == 4.8e9 and publie["revenue_estimate"] is None


def test_yfinance_un_titre_en_panne_n_empeche_pas_les_autres(yf):
    yf.pannes = {"BAD"}
    rows = e._yf_earnings(["BAD", "AAPL"], days_back=21, days_fwd=30)
    assert {r["symbol"] for r in rows} == {"AAPL"}


def test_yfinance_absent_rend_vide(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", None)        # import → ImportError
    assert e._yf_earnings(["AAPL"]) == []


def test_earnings_for_fmp_prioritaire_puis_tri_a_venir_d_abord(monkeypatch):
    lignes = [{"symbol": "A", "date": _j(-3).isoformat()},
              {"symbol": "B", "date": _j(20).isoformat()},
              {"symbol": "C", "date": ""},                  # non datée : écartée
              {"symbol": "D", "date": _j(2).isoformat()}]
    monkeypatch.setattr(e, "_fmp_earnings", lambda s, b, f: list(lignes))
    monkeypatch.setattr(e, "_yf_earnings", lambda *a: pytest.fail("repli inutile"))
    ordre = [r["symbol"] for r in e.earnings_for(["a", "b", None, "d"])]
    assert ordre == ["D", "B", "A"]


def test_earnings_for_retombe_sur_yfinance_quand_fmp_est_vide(monkeypatch):
    vu = {}
    monkeypatch.setattr(e, "_fmp_earnings", lambda s, b, f: [])

    def yf(syms, b, f):
        vu["syms"] = syms
        return [{"symbol": "AAPL", "date": _j(1).isoformat()}]
    monkeypatch.setattr(e, "_yf_earnings", yf)
    assert e.earnings_for(["aapl", ""])[0]["symbol"] == "AAPL"
    assert vu["syms"] == ["AAPL"]
