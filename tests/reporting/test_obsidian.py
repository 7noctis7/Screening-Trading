"""Quant Obsidian Vault — tests purs (builders Markdown, attribution, incidents, écriture atomique)."""

import pathlib

from packages.reporting import obsidian as O


def _snap(max_dd=-0.12, breach_label="MU", dd_now_curve=True, var_reject=False):
    curve = [100 * (1.02 ** i) for i in range(120)]
    if not dd_now_curve:                                   # force un gros drawdown courant (chute finale)
        curve = curve + [curve[-1] * 0.6]
    return {
        "dashboard": {"vix": 22.0, "strategy_label": "50% QQQ + preset",
                      "regime": {"cycle": "slowdown", "risk_mode": "risk_off"},
                      "metrics": {"total_return": 1.2, "sharpe": 0.9, "sortino": 0.8, "calmar": 0.5,
                                  "max_drawdown": max_dd},
                      "positions": [{"symbol": "QQQ", "sector": "ETF", "weight": 0.5},
                                    {"symbol": "MU", "sector": "Tech", "weight": 0.3}]},
        "portfolio": {"analysis": {
            "risk": {"var_95": 0.02, "cvar_95": 0.03, "garch": {"vol_forecast": 0.18},
                     "var_backtest": {"reject": var_reject}},
            "limits": {"ok": False, "top_name": "QQQ", "top_name_weight": 0.5,
                       "breaches": [{"type": "nom", "label": breach_label, "weight": 0.3, "limit": 0.2}]}}},
        "preset_ledger": {"summary": {"fees_paid": 19.0, "fees_pct": 0.0019, "reconciles": True}},
        "index_core_curves": {"preset": curve, "qqq": [100 * (1.015 ** i) for i in range(len(curve))]},
    }


def test_attribution_capm():
    a = O.compute_attribution(_snap())
    assert a["available"] is True
    assert "alpha_annual" in a and "beta_qqq" in a and 0.0 <= a["r2"] <= 1.0


def test_incident_ignores_intentional_core_breach():
    # breach sur QQQ (cœur intentionnel) → PAS d'incident de limite
    inc = O.detect_incidents(_snap(breach_label="QQQ"))
    assert not any(i["type"] == "limite_risque" for i in inc)
    # breach sur un nom non-core → incident
    inc2 = O.detect_incidents(_snap(breach_label="MU"))
    assert any(i["type"] == "limite_risque" for i in inc2)


def test_kill_switch_uses_current_drawdown():
    assert not any(i["type"] == "kill_switch_drawdown" for i in O.detect_incidents(_snap()))       # proche du peak
    inc = O.detect_incidents(_snap(dd_now_curve=False))                                              # chute de 40 %
    assert any(i["type"] == "kill_switch_drawdown" for i in inc)


def test_var_kupiec_incident():
    assert any(i["type"] == "var_backtest_kupiec" for i in O.detect_incidents(_snap(var_reject=True)))


def test_daily_note_structure_and_frontmatter():
    s = _snap(dd_now_curve=False)
    rel, md = O.daily_note(s, O.compute_attribution(s), O.detect_incidents(s), "2026-06-20")
    assert rel == "03_Journal/2026-06-20.md"
    assert md.startswith("---") and "type: daily_journal" in md and "date: 2026-06-20" in md
    assert "**Risque**" in md and "## Métriques clés" in md     # statut risque concis (ex-mermaid)
    assert "KILL-SWITCH ACTIF" in md and "[[Preset_Performance]]" in md


def test_incident_note_captures_book():
    s = _snap()
    rel, md = O.incident_note(s, {"type": "limite_risque", "detail": "x"}, "2026-06-20")
    assert rel == "04_Post_Mortem/incident_2026-06-20.md"
    assert "[[QQQ]]" in md and "[!danger]" in md and "type: incident" in md


def test_sync_atomic_and_isolated(tmp_path):
    s = _snap(dd_now_curve=False)
    res = O.sync_obsidian_vault(snapshot=s, root=tmp_path)
    assert res["ok"] is True
    assert (tmp_path / "03_Journal" / "2026-06-20.md").exists() or any("03_Journal" in w for w in res["written"])
    assert (tmp_path / "Preset_Performance.md").exists()
    assert res["incidents"] >= 1                          # kill-switch + ... généré


def test_sync_never_raises_on_bad_snapshot(tmp_path):
    # snapshot vide / cassé → ne lève pas, renvoie ok avec coffre minimal
    res = O.sync_obsidian_vault(snapshot={}, root=tmp_path)
    assert isinstance(res, dict) and "ok" in res


def test_weekly_note_structure():
    s = _snap()
    s["dashboard"]["preset_allocation"] = [{"symbol": "MU", "sector": "Tech", "weight": 0.08}]
    s["dashboard"]["chart_series"] = {"MU": [{"c": 100 + i} for i in range(10)]}
    rel, md = O.weekly_note(s, O.compute_attribution(s), "2026-06-20")
    assert rel.startswith("06_Weekly/") and rel.endswith(".md")
    assert "type: weekly_review" in md and "Synthèse hebdomadaire" in md
    assert "[[Preset_Performance]]" in md and "[[MU]]" in md          # contributeur lié
