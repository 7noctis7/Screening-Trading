"""Note d'analyse par société — audit PwC, structure, rendu HTML."""
from datetime import datetime, timezone

from packages.fundamentals.models import Financials
from packages.reporting import (
    audit_financials,
    build_company_report,
    company_report_html,
    company_report_markdown,
)
from packages.reporting.company_report import sector_positioning, technical_score


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
    for token in ("Vernimmen", "Damodaran", "Audit d'intégrité", "NVIDIA", "ROCE", "WACC", "Verdict"):
        assert token in html


def test_pillars_sum_weights_to_one():
    r = build_company_report(_fin(), name="NVIDIA")
    assert abs(sum(p["weight"] for p in r["score"]["pillars"].values()) - 1.0) < 1e-9


def test_markdown_obsidian_note():
    r = build_company_report(_fin(), name="NVIDIA", beta=1.5,
                             peers=[{"net_margin": 0.1, "roe": 0.1, "roic": 0.1, "gross_margin": 0.3,
                                     "per": 30, "ev_ebitda": 20} for _ in range(5)])
    md = company_report_markdown(r)
    assert md.startswith("---") and "type: company_report" in md   # front matter Dataview
    assert "tags: [quant, company]" in md and "# 🏢 NVIDIA" in md
    assert "ROCE" in md and "DCF base" in md and "Vigilance" in md or "Forces" in md


def test_valuation_gate_masks_currency_mismatch():
    # ADR : comptes en devise locale (revenue/net_income géants) vs cours USD → valorisation masquée
    f = _fin(price=462.0, shares=5.2e9, revenue=2.159e12, gross_profit=1.3e12, ebit=1.1e12,
             ebitda=1.4e12, net_income=1.0e12, total_equity=2.0e12, total_debt=3e11, cash=1.5e12, fcf=8e11)
    r = build_company_report(f, name="TSMC", beta=1.0)
    assert r["damodaran"]["dcf"]["reliable"] is False
    assert r["damodaran"]["dcf"]["margin_of_safety"] is None        # MoS aberrante masquée
    assert any("devise" in x["detail"] or "unités" in x["detail"] for x in r["audit"]["findings"])
    html = company_report_html(r)
    assert "Valorisation non fiable" in html


def test_valuation_plausible_stays_reliable():
    r = build_company_report(_fin(), name="NVIDIA")               # valeurs USD cohérentes
    assert r["damodaran"]["dcf"]["reliable"] is True


def test_charts_have_numeric_axes():
    closes = [100 + i * 0.4 for i in range(260)]
    dates = [f"2025-{1 + i % 12:02d}-15" for i in range(260)]
    r = build_company_report(_fin(), name="X", price_series=closes, price_dates=dates,
                             financial_history=[{"year": y, "revenue": 1e10 * (y - 2019),
                                                 "net_income": 2e9 * (y - 2019)} for y in range(2020, 2025)])
    assert r["charts"]["price_labels"]                            # dates pour l'axe X
    html = company_report_html(r)
    assert 'text-anchor="end"' in html and "$" in html           # labels d'axe Y chiffrés


def test_theme_light_and_dark():
    r = build_company_report(_fin(), name="NVIDIA")
    dark = company_report_html(r, theme="dark")
    light = company_report_html(r, theme="light")
    assert "#0b0d10" in dark and "background:#0b0d10" in dark        # fond sombre
    assert "background:#ffffff" in light                             # fond clair
    assert dark != light


def test_more_content_multiples_and_findata():
    hist = [{"year": y, "revenue": 1e10 * (y - 2019), "net_income": 2e9 * (y - 2019), "eps": y - 2019}
            for y in range(2020, 2025)]
    r = build_company_report(_fin(), name="NVIDIA", financial_history=hist)
    html = company_report_html(r)
    assert "Multiples : P/E" in html                                 # multiples toujours affichés
    assert "Données financières" in html and "Marge nette" in html   # tableau chiffré par exercice


def test_memo_present_and_rendered():
    r = build_company_report(_fin(), name="NVIDIA", beta=1.5)
    assert r["memo"] and "NVIDIA" in r["memo"] and r["memo_source"] == "synthèse (règles)"
    html = company_report_html(r)
    assert "Synthèse" in html and r["memo"][:20] in html


def test_sector_positioning_direction_aware():
    peers = [{"net_margin": 0.10, "per": 30}, {"net_margin": 0.12, "per": 25},
             {"net_margin": 0.15, "per": 20}, {"net_margin": 0.20, "per": 18}]
    # société : marge élevée (favorable) + P/E bas (favorable)
    comp = {"net_margin": 0.30, "per": 15}
    res = sector_positioning(comp, peers)
    assert res["available"]
    by = {r["metric"]: r for r in res["rows"]}
    assert by["net_margin"]["verdict"] == "favorable" and by["net_margin"]["percentile"] == 1.0
    assert by["per"]["verdict"] == "favorable"             # P/E plus bas que tous → favorable


def test_sector_positioning_needs_min_peers():
    res = sector_positioning({"net_margin": 0.2}, [{"net_margin": 0.1}])
    assert not res["available"]                            # <3 valeurs → pas de positionnement


def test_report_includes_sector_comparison():
    peers = [{"net_margin": 0.1, "roe": 0.1, "roic": 0.1, "gross_margin": 0.3, "per": 30, "ev_ebitda": 20}
             for _ in range(5)]
    r = build_company_report(_fin(), name="NVIDIA", peers=peers)
    sc = r["sector_comparison"]
    assert sc["available"] and sc["total"] >= 1
    assert "Positionnement sectoriel" in company_report_html(r)


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


def test_charts_block_and_svg_render():
    closes = [100 + i * 0.5 for i in range(260)]              # tendance régulière
    r = build_company_report(_fin(price=closes[-1]), name="NVIDIA",
                             prior=_fin(revenue=1.2e11, net_income=6e10),
                             price_series=closes)
    ch = r["charts"]
    assert len(ch["price"]) > 0 and len(ch["financial_history"]) == 2   # N-1 + N
    html = company_report_html(r)
    assert "Graphiques" in html and "<svg" in html and "Drawdown" in html


def test_charts_derive_history_from_prior():
    r = build_company_report(_fin(), name="X", prior=_fin(revenue=1e11, net_income=5e10))
    hist = r["charts"]["financial_history"]
    assert [h["year"] for h in hist][0] < [h["year"] for h in hist][1]   # N-1 puis N


def test_multiyear_history_computes_cagr():
    hist = [{"year": 2020, "revenue": 1.0e10, "net_income": 2e9},
            {"year": 2021, "revenue": 1.5e10, "net_income": 3e9},
            {"year": 2022, "revenue": 2.0e10, "net_income": 4e9},
            {"year": 2023, "revenue": 3.0e10, "net_income": 6e9},
            {"year": 2024, "revenue": 4.0e10, "net_income": 9e9}]
    r = build_company_report(_fin(), name="NVIDIA", financial_history=hist)
    ch = r["charts"]
    assert ch["history_years"] == 5 and ch["revenue_cagr"] is not None
    # CAGR (1e10→4e10 sur 4 ans) ≈ 41.4 %
    assert abs(ch["revenue_cagr"] - ((4.0e10 / 1.0e10) ** (1 / 4) - 1)) < 1e-3   # arrondi 4 déc.
    assert "CAGR" in company_report_html(r)


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
