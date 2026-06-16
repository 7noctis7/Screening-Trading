"""Génère un aperçu HTML statique du dashboard depuis les vraies données du snapshot.

Rendu côté Python (aucun build, aucun JS) → ouvrable directement. Reflète le design
system (dark, sobre, vert/rouge réservés au P&L) et les payloads réels de l'API.

  python apps/web/preview/build_preview.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from apps.api.snapshot import build_snapshot  # noqa: E402

C = {"bg": "#0a0b0d", "surface": "#141619", "border": "#262a31", "fg": "#e6e8eb",
     "muted": "#9aa1ab", "accent": "#3b82f6", "pos": "#22c55e", "neg": "#ef4444"}
CYCLE = {"expansion": "#22c55e", "recovery": "#3b82f6", "slowdown": "#f59e0b",
         "recession": "#ef4444"}


def _polyline(values, w, h, pad=4):
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1.0
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = pad + i * (w - 2 * pad) / (n - 1)
        y = h - pad - (v - lo) / rng * (h - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def _card(inner):
    return (f'<div style="background:{C["surface"]};border:1px solid {C["border"]};'
            f'border-radius:16px;padding:18px">{inner}</div>')


def _metric(label, value, tone=None):
    color = C.get(tone, C["fg"])
    return _card(
        f'<div style="color:{C["muted"]};font-size:11px;text-transform:uppercase;'
        f'letter-spacing:.06em">{label}</div>'
        f'<div style="font-size:26px;margin-top:6px;color:{color};'
        f'font-variant-numeric:tabular-nums">{value}</div>')


def build_html() -> str:
    s = build_snapshot()
    d, scr, pf = s["dashboard"], s["screener"], s["portfolio"]
    rg, m = d["regime"], d["metrics"]
    pct = lambda x: f"{x * 100:+.1f}%"  # noqa: E731

    eq = [p["v"] for p in d["equity"]]
    bench = pf["benchmarks"]
    port_line = _polyline(bench.get("portfolio", []), 720, 180)
    sp_line = _polyline(bench.get("S&P 500", []), 720, 180)

    cyc_color = CYCLE.get(rg["cycle"], C["muted"])
    banner = _card(
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<div style="display:flex;gap:10px;align-items:center">'
        f'<span style="height:10px;width:10px;border-radius:50%;background:{cyc_color}"></span>'
        f'<span style="font-weight:600;text-transform:capitalize">{rg["cycle"]}</span>'
        f'<span style="color:{C["muted"]}">· {rg["risk_mode"]}</span></div>'
        f'<div style="color:{C["muted"]};font-variant-numeric:tabular-nums">'
        f'courbe 2s10s {rg["extras"].get("curve_2s10s","—")} · VIX {rg.get("vix",0):.0f} · '
        f'exposition ×{rg["exposure_multiplier"]}</div></div>')

    metrics = (
        _metric("Rendement", pct(m["total_return"]), "pos" if m["total_return"] >= 0 else "neg")
        + _metric("Sharpe", f'{m["sharpe"]:.2f}')
        + _metric("Sortino", f'{m["sortino"]:.2f}')
        + _metric("Max Drawdown", pct(m["max_drawdown"]), "neg"))

    chart = _card(
        f'<div style="color:{C["muted"]};font-size:11px;text-transform:uppercase;'
        f'letter-spacing:.06em;margin-bottom:10px">Equity vs S&amp;P 500 (rebasé 100)</div>'
        f'<svg viewBox="0 0 720 180" width="100%" height="180">'
        f'<polyline points="{sp_line}" fill="none" stroke="{C["muted"]}" '
        f'stroke-width="1.5" opacity="0.6"/>'
        f'<polyline points="{port_line}" fill="none" stroke="{C["accent"]}" stroke-width="2"/>'
        f'</svg>')

    rows = ""
    for r in scr["rows"][:8]:
        rows += (f'<tr style="border-top:1px solid {C["border"]}">'
                 f'<td style="padding:7px 0;color:{C["muted"]}">{r["rank"]}</td>'
                 f'<td style="font-weight:500">{r["symbol"]}</td>'
                 f'<td style="text-align:right;font-variant-numeric:tabular-nums">{r["score"]:.3f}</td>'
                 f'<td style="padding-left:16px;color:{C["muted"]}">{r["reason"] or ""}</td></tr>')
    screener = _card(
        f'<div style="color:{C["muted"]};font-size:11px;text-transform:uppercase;'
        f'letter-spacing:.06em;margin-bottom:10px">Top screener multi-facteur</div>'
        f'<table style="width:100%;border-collapse:collapse;font-size:14px">'
        f'<tr style="color:{C["muted"]};font-size:11px;text-align:left">'
        f'<th>#</th><th>Actif</th><th style="text-align:right">Score</th>'
        f'<th style="padding-left:16px">Facteurs dominants</th></tr>{rows}</table>')

    tot = pf["totals"]
    pos_tone = "pos" if tot["pnl_abs"] >= 0 else "neg"
    footer = _card(
        f'<div style="display:flex;justify-content:space-between;color:{C["muted"]};font-size:13px">'
        f'<span>Exposition brute {tot["gross_exposure"]:,.0f} · nette {tot["net_exposure"]:,.0f}</span>'
        f'<span style="color:{C[pos_tone]};font-variant-numeric:tabular-nums">'
        f'P&amp;L {tot["pnl_abs"]:+,.0f} ({pct(tot["pnl_pct"])})</span></div>')

    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quant Terminal — aperçu</title></head>
<body style="margin:0;background:{C['bg']};color:{C['fg']};
font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Inter,system-ui,sans-serif">
<div style="max-width:780px;margin:0 auto;padding:24px;display:flex;flex-direction:column;gap:14px">
<div style="display:flex;justify-content:space-between;align-items:baseline">
<h1 style="font-size:20px;font-weight:600;letter-spacing:-.02em;margin:0">Quant Terminal</h1>
<span style="color:{C['muted']};font-size:12px">aperçu statique · données synthétiques</span></div>
{banner}
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">{metrics}</div>
{chart}{screener}{footer}
</div></body></html>"""


if __name__ == "__main__":
    write_all()


def _heatmap_cell(v):
    # bleu (corr -1) → gris (0) → rouge (corr +1)
    r = int(120 + 100 * max(0, v)); b = int(120 + 100 * max(0, -v)); g = 100
    return f"rgb({r},{g},{b})"


def build_portfolio_html() -> str:
    s = build_snapshot()
    pf = s["portfolio"]; an = pf["analysis"]
    rel, rm, mc, rev = an["relative"], an["risk"], an["monte_carlo"], an["review"]
    corr = an["correlation"]; pct = lambda x: f"{x*100:.1f}%"  # noqa: E731

    rel_rows = "".join(
        f'<tr style="border-top:1px solid {C["border"]}"><td style="padding:6px 0;color:{C["muted"]}">{k}</td>'
        f'<td style="text-align:right;font-variant-numeric:tabular-nums">{v}</td></tr>'
        for k, v in rel.items())
    rel_card = _card(
        f'<div style="color:{C["muted"]};font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Mesures relatives (vs S&amp;P 500)</div>'
        f'<table style="width:100%;font-size:13px">{rel_rows}</table>')

    risk_card = _card(
        f'<div style="color:{C["muted"]};font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Risque (FRM)</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:13px">'
        f'<div><div style="color:{C["muted"]}">VaR 95%</div><div style="font-size:18px">{pct(rm["var_95"])}</div></div>'
        f'<div><div style="color:{C["muted"]}">CVaR 95%</div><div style="font-size:18px">{pct(rm["cvar_95"])}</div></div>'
        f'<div><div style="color:{C["muted"]}">Vol (période)</div><div style="font-size:18px">{pct(rm["vol"])}</div></div>'
        f'<div><div style="color:{C["muted"]}">Proba ruine (MC)</div><div style="font-size:18px">{pct(mc["p_ruin"])}</div></div>'
        f'</div>')

    # heatmap
    syms = corr["symbols"]; M = corr["matrix"]
    head = "".join(f'<th style="font-weight:400;color:{C["muted"]};font-size:11px;padding:2px">{s}</th>' for s in syms)
    grid = ""
    for i, row in enumerate(M):
        cells = "".join(
            f'<td style="background:{_heatmap_cell(v)};color:#fff;text-align:center;'
            f'font-size:11px;padding:6px;border-radius:4px">{v:+.2f}</td>' for v in row)
        grid += f'<tr><th style="color:{C["muted"]};font-size:11px;padding:2px;text-align:right">{syms[i]}</th>{cells}</tr>'
    heat = _card(
        f'<div style="color:{C["muted"]};font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Corrélation du portefeuille · clusters: {corr["clusters"]}</div>'
        f'<table style="border-collapse:separate;border-spacing:3px"><tr><th></th>{head}</tr>{grid}</table>')

    def lst(title, items, color):
        if not items:
            return ""
        lis = "".join(f'<li style="margin:3px 0">{x}</li>' for x in items)
        return f'<div style="margin-bottom:8px"><div style="color:{color};font-size:12px;font-weight:600">{title}</div><ul style="margin:4px 0 0;padding-left:18px;font-size:13px;color:{C["fg"]}">{lis}</ul></div>'

    score = rev["health_score"]
    score_color = C["pos"] if score >= 65 else (C["neg"] if score < 45 else "#f59e0b")
    review = _card(
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'
        f'<div style="color:{C["muted"]};font-size:11px;text-transform:uppercase;letter-spacing:.06em">Revue experte (CFA/FRM/CPA/CAIA)</div>'
        f'<div style="font-size:28px;color:{score_color};font-variant-numeric:tabular-nums">{score}<span style="font-size:13px;color:{C["muted"]}">/100</span></div></div>'
        + lst("Forces", rev["strengths"], C["pos"])
        + lst("Faiblesses", rev["weaknesses"], "#f59e0b")
        + lst("Risques", rev["risks"], C["neg"])
        + lst("Recommandations", rev["recommendations"], C["accent"])
        + f'<div style="color:{C["muted"]};font-size:11px;margin-top:8px;font-style:italic">{rev["disclaimer"]}</div>')

    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Portefeuille — aperçu</title></head>
<body style="margin:0;background:{C['bg']};color:{C['fg']};font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Inter,system-ui,sans-serif">
<div style="max-width:780px;margin:0 auto;padding:24px;display:flex;flex-direction:column;gap:14px">
<h1 style="font-size:20px;font-weight:600;letter-spacing:-.02em;margin:0">Portefeuille &amp; Analyse</h1>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">{rel_card}{risk_card}</div>
{heat}{review}
</div></body></html>"""


def write_all():
    here = Path(__file__).resolve().parent
    (here / "dashboard.html").write_text(build_html(), encoding="utf-8")
    (here / "portfolio.html").write_text(build_portfolio_html(), encoding="utf-8")
    print("écrit : dashboard.html + portfolio.html")


if __name__ == "__main__":
    write_all()
