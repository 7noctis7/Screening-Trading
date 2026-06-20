"""Note d'analyse par société — audit PwC, structure, rendu HTML."""
from datetime import datetime, timezone

from packages.fundamentals.models import Financials
from packages.reporting import (
    audit_financials,
    build_company_report,
    company_report_html,
)
from packages.reporting.company_report import technical_score


def _fin(**kw) -> Financials:
    base = dict(symbol="NVDA", as_of=datetime.now(timezone.utc), sector="Information Technology",
                price=210.0, shares=2.4e10, revenue=2.159e11, gross_profit=1.535e11, ebit=1.3e11,
                ebitda=1.4e11, net_income=1.36e11, total_equity=8.84e10, total_debt=1e10, cash=5e10,
                fcf=1.027e11, interest_expense=2e8, revenue_growth=0.85)
    base.update(kw)
    return Financials(**base)


def test_audit_clean_is_reliable():
    a = audit_financials(_fin())
    assert a["ok"] and a["reliability"] in ("fiable", "à vérifier")


def test_audit_flags_negative_revenue_critical():
    a = audit_financials(_fin(revenue=-1.0))
    assert not a["ok"] and a["counts"]["critical"] >= 1


def test_audit_flags_margin_incoherence():
    a = audit_financials(_fin(gross_profit=3e11))            # marge brute > CA
    assert a["counts"]["major"] >= 1


def test_report_structure_complete():
    r = build_company_report(_fin(), name="NVIDIA", beta=1.6)
    for key in ("identity", "audit", "score", "vernimmen", "damodaran", "quality", "verdict"):
        assert key in r
    assert 0 <= r["score"]["global"] <= 100
    assert r["score"]["recommendation"] in ("Achat", "Conserver", "Vente")
    assert r["vernimmen"]["roce_after_tax"] is not None
    assert "scenarios" in r["damodaran"]["dcf"]


def test_report_value_creation_detected():
    r = build_company_report(_fin(), name="NVIDIA", beta=1.6)
    # NVIDIA très rentable → ROCE > WACC → spread positif
    assert r["vernimmen"]["value_creation_spread"] > 0


def test_html_render_contains_sections():
    html = company_report_html(build_company_report(_fin(), name="NVIDIA", beta=1.6))
    assert html.startswith("<!doctype html>")
    for token in ("Vernimmen", "Damodaran", "PwC", "NVIDIA", "ROCE", "WACC", "Verdict"):
        assert token in html


def test_pillars_sum_weights_to_one():
    r = build_company_report(_fin(), name="NVIDIA")
    assert abs(sum(p["weight"] for p in r["score"]["pillars"].values()) - 1.0) < 1e-9


def test_technical_score_directional():
    bull = technical_score({"trend": "haussière", "macd_signal": "haussier", "rsi": 55,
                            "vs_sma50": 0.05, "vs_sma200": 0.10})
    bear = technical_score({"trend": "baissière", "macd_signal": "baissier", "rsi": 40,
                            "vs_sma50": -0.05, "vs_sma200": -0.10})
    assert bull > bear and 0 <= bear <= 100 and 0 <= bull <= 100
    assert technical_score(None) is None


def test_three_scores_present_and_global_blends():
    r = build_company_report(_fin(), name="NVIDIA", beta=1.4,
                             technical={"trend": "haussière", "macd_signal": "haussier", "rsi": 58,
                                        "vs_sma50": 0.04, "vs_sma200": 0.08},
                             ml_score=0.72)
    sc = r["score"]
    assert sc["fundamental"] is not None and sc["technical"] is not None and sc["ml"] == 72
    assert 0 <= sc["global"] <= 100


def test_optional_sections_rendered():
    r = build_company_report(_fin(), name="NVIDIA",
                             technical={"trend": "haussière", "rsi": 55, "macd_signal": "haussier",
                                        "vs_sma50": 0.03, "vs_sma200": 0.06, "low_52w": 100, "high_52w": 300},
                             macro={"regime": "expansion", "vix": 16.4, "exposure": 0.8},
                             earnings={"next_date": "2026-08-20", "eps_estimate": 1.2, "eps_actual": 1.3,
                                       "revenue_estimate": 5e10, "revenue_actual": 5.3e10})
    html = company_report_html(r)
    for tok in ("Analyse technique", "macro", "estimations", "2026-08-20"):
        assert tok in html
