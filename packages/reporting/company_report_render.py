"""Rendu de la note d'analyse — HTML autonome (toujours) + PDF (reportlab si présent).

Design « Apple-quality » : sobre, dense, hiérarchie claire, typographie système, jauges SVG.
HTML imprimable (Ctrl-P → PDF) partout, même sans reportlab. Aucune dépendance dure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_C = {"bg": "#0b0d10", "card": "#14171b", "card2": "#1a1e24", "border": "#262b33",
      "fg": "#e8eaed", "muted": "#9aa1ab", "accent": "#22d3ee", "pos": "#22c55e",
      "warn": "#f59e0b", "neg": "#ef4444", "blue": "#3b82f6"}


def _pct(x: float | None, nd: int = 1) -> str:
    return "—" if x is None else f"{x*100:.{nd}f}%"


def _num(x: float | None, nd: int = 2) -> str:
    return "—" if x is None else f"{x:,.{nd}f}".replace(",", " ")


def _money(x: float | None) -> str:
    if x is None:
        return "—"
    a = abs(x)
    for div, suf in ((1e12, "T"), (1e9, "Md"), (1e6, "M")):
        if a >= div:
            return f"${x/div:.1f} {suf}"
    return f"${x:,.0f}".replace(",", " ")


def _tone(score: int) -> str:
    return _C["pos"] if score >= 65 else _C["warn"] if score >= 45 else _C["neg"]


def _gauge(score: int, size: int = 96) -> str:
    """Jauge circulaire SVG (score /100)."""
    r = size / 2 - 8
    c = 2 * 3.14159 * r
    off = c * (1 - max(0, min(100, score)) / 100)
    col = _tone(score)
    cx = size / 2
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="{_C["border"]}" stroke-width="8"/>'
            f'<circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="{col}" stroke-width="8" '
            f'stroke-linecap="round" stroke-dasharray="{c:.1f}" stroke-dashoffset="{off:.1f}" '
            f'transform="rotate(-90 {cx} {cx})"/>'
            f'<text x="{cx}" y="{cx-2}" text-anchor="middle" font-size="26" font-weight="700" '
            f'fill="{_C["fg"]}">{score}</text>'
            f'<text x="{cx}" y="{cx+16}" text-anchor="middle" font-size="10" fill="{_C["muted"]}">/100</text></svg>')


def _bar(score: int) -> str:
    col = _tone(score)
    return (f'<div style="height:6px;background:{_C["border"]};border-radius:3px;overflow:hidden">'
            f'<div style="height:100%;width:{max(0,min(100,score))}%;background:{col}"></div></div>')


def _card(title: str, inner: str) -> str:
    return (f'<section style="background:{_C["card"]};border:1px solid {_C["border"]};border-radius:16px;'
            f'padding:18px;margin-bottom:14px">'
            f'<h2 style="font-size:12px;text-transform:uppercase;letter-spacing:.06em;'
            f'color:{_C["muted"]};margin:0 0 12px">{title}</h2>{inner}</section>')


def _kv_grid(items: list[tuple[str, str, str]]) -> str:
    """Grille label/valeur (label, valeur, couleur)."""
    cells = "".join(
        f'<div><div style="color:{_C["muted"]};font-size:11px">{lab}</div>'
        f'<div style="font-size:17px;font-variant-numeric:tabular-nums;color:{col}">{val}</div></div>'
        for lab, val, col in items)
    return (f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));'
            f'gap:14px">{cells}</div>')


def _findings_html(audit: dict) -> str:
    sev_col = {"critical": _C["neg"], "major": _C["warn"], "warning": _C["muted"]}
    rel_col = {"fiable": _C["pos"], "à vérifier": _C["warn"], "non fiable": _C["neg"]}
    rows = "".join(
        f'<li style="color:{sev_col.get(x["severity"], _C["muted"])};font-size:12px;margin:2px 0">'
        f'[{x["severity"]}] {x["detail"]}</li>' for x in audit.get("findings", []))
    body = f'<ul style="margin:8px 0 0;padding-left:18px">{rows}</ul>' if rows else \
        f'<p style="color:{_C["pos"]};font-size:12px;margin:6px 0 0">✓ Aucune anomalie — données cohérentes.</p>'
    c = audit.get("counts", {})
    badge = (f'<span style="color:{rel_col.get(audit.get("reliability"), _C["muted"])};font-weight:600">'
             f'{audit.get("reliability", "—")}</span>')
    return (f'<div style="font-size:12px;color:{_C["muted"]}">Verdict fiabilité : {badge} · '
            f'{c.get("critical",0)} critiques · {c.get("major",0)} majeures · {c.get("warning",0)} avert.</div>'
            f'{body}')


def company_report_html(r: dict[str, Any]) -> str:
    idy, sc, ver, dam, ql = r["identity"], r["score"], r["vernimmen"], r["damodaran"], r["quality"]
    audit = r["audit"]
    g = sc["global"]

    # piliers
    pillars = "".join(
        f'<div style="margin:8px 0"><div style="display:flex;justify-content:space-between;'
        f'font-size:12px;margin-bottom:3px"><span>{name}</span>'
        f'<span style="color:{_tone(p["score"])};font-variant-numeric:tabular-nums">{p["score"]}</span></div>'
        f'{_bar(p["score"])}</div>' for name, p in sc["pillars"].items())

    # trois scores : fondamental / technique / ML
    def _mini(label: str, val: int | None) -> str:
        if val is None:
            return (f'<div style="text-align:center"><div style="font-size:11px;color:{_C["muted"]}">{label}</div>'
                    f'<div style="font-size:18px;color:{_C["muted"]}">—</div></div>')
        return (f'<div style="text-align:center"><div style="font-size:11px;color:{_C["muted"]}">{label}</div>'
                f'<div style="font-size:18px;font-weight:700;color:{_tone(val)}">{val}'
                f'<span style="font-size:10px;color:{_C["muted"]}">/100</span></div></div>')
    sub_scores = (f'<div style="display:flex;gap:18px;margin-top:8px">'
                  f'{_mini("Fondamental", sc.get("fundamental"))}'
                  f'{_mini("Technique", sc.get("technical"))}'
                  f'{_mini("ML", sc.get("ml"))}</div>')

    # en-tête
    header = (
        f'<div style="display:flex;align-items:center;gap:20px;margin-bottom:18px">'
        f'<div>{_gauge(g)}</div>'
        f'<div style="flex:1"><div style="font-size:24px;font-weight:700">{idy["name"]} '
        f'<span style="color:{_C["muted"]};font-size:16px">{idy["symbol"]}</span></div>'
        f'<div style="color:{_C["muted"]};font-size:13px">{idy["sector"]} · {_money(idy["market_cap"])} de capi · '
        f'cours ${_num(idy["price"])}</div>'
        f'<div style="margin-top:6px;display:inline-block;padding:3px 12px;border-radius:999px;'
        f'background:{_tone(g)}22;color:{_tone(g)};font-weight:600;font-size:13px">'
        f'{sc["recommendation"]} · {g}/100</div>'
        f'{sub_scores}</div></div>')

    # Vernimmen
    spread = ver.get("value_creation_spread")
    vern = _kv_grid([
        ("ROCE après impôt", _pct(ver.get("roce_after_tax")), _C["fg"]),
        ("WACC", _pct(ver.get("wacc")), _C["fg"]),
        ("Spread ROCE−WACC", _pct(spread) if spread is not None else "—",
         _C["pos"] if (spread or 0) > 0 else _C["neg"]),
        ("EVA (profit éco.)", _money(ver.get("eva")), _C["pos"] if (ver.get("eva") or 0) > 0 else _C["neg"]),
        ("Gearing (DN/CP)", _num(ver.get("gearing")), _C["fg"]),
        ("Dette nette/EBITDA", _num(ver.get("net_debt_ebitda"), 1) + "×", _C["fg"]),
    ])
    m = ver["margins"]; dpt = ver["dupont"]
    vern += (f'<div style="margin-top:12px;font-size:12px;color:{_C["muted"]}">'
             f'Marges : brute {_pct(m.get("gross"))} · EBIT {_pct(m.get("ebit"))} · nette {_pct(m.get("net"))}'
             f'&nbsp;&nbsp;|&nbsp;&nbsp;DuPont ROE = marge {_pct(dpt.get("net_margin"))} × '
             f'rotation {_num(dpt.get("asset_turnover"))} × levier {_num(dpt.get("equity_multiplier"))} '
             f'= <b style="color:{_C["fg"]}">{_pct(dpt.get("roe"))}</b></div>')

    # Damodaran
    dcf = dam["dcf"]; scen = dcf.get("scenarios", {})
    mos = dcf.get("margin_of_safety")
    dam_kv = _kv_grid([
        ("Coût des FP (MEDAF)", _pct(dam.get("cost_of_equity")), _C["fg"]),
        ("WACC", _pct(dam.get("wacc")), _C["fg"]),
        ("Bêta", _num(dam.get("beta")), _C["fg"]),
        ("DCF bear", "$" + _num(scen.get("bear")), _C["muted"]),
        ("DCF base", "$" + _num(scen.get("base")), _C["fg"]),
        ("DCF bull", "$" + _num(scen.get("bull")), _C["muted"]),
        ("Marge de sécurité", _pct(mos) if mos is not None else "—",
         _C["pos"] if (mos or 0) > 0 else _C["neg"]),
        ("Croiss. implicite (cours)", _pct(dam.get("implied_growth_in_price")), _C["fg"]),
    ])
    # multiples vs secteur
    mvs = dam.get("multiples_vs_sector", {})
    if mvs:
        rows = "".join(
            f'<tr style="border-top:1px solid {_C["border"]}"><td style="padding:4px 0">{k.upper()}</td>'
            f'<td style="text-align:right">{_num(v.get("company"))}</td>'
            f'<td style="text-align:right;color:{_C["muted"]}">{_num(v.get("sector"))}</td></tr>'
            for k, v in mvs.items())
        dam_kv += (f'<table style="width:100%;font-size:12px;margin-top:12px"><thead>'
                   f'<tr style="color:{_C["muted"]}"><th style="text-align:left">Multiple</th>'
                   f'<th style="text-align:right">Société</th><th style="text-align:right">Secteur</th></tr>'
                   f'</thead><tbody>{rows}</tbody></table>')

    # Qualité
    z = ql["altman_z"]; inv = ql["investor_scores"]
    qual = _kv_grid([
        ("Piotroski F-score", f'{ql["piotroski_f_score"]}/9 ({ql["piotroski_label"]})', _C["fg"]),
        ("Altman Z", (f'{z.get("z")} ({z.get("zone")})' if z.get("z") is not None else "N/A"), _C["fg"]),
        ("Graham", f'{inv.get("graham")}/100', _C["fg"]),
        ("Fisher", f'{inv.get("fisher")}/100', _C["fg"]),
        ("Thiel", f'{inv.get("thiel")}/100', _C["fg"]),
    ])

    # Verdict
    v = r["verdict"]
    st = "".join(f'<li style="color:{_C["pos"]};font-size:12px;margin:2px 0">✓ {s}</li>' for s in v["strengths"])
    wt = "".join(f'<li style="color:{_C["warn"]};font-size:12px;margin:2px 0">▸ {s}</li>' for s in v["watch"])
    verdict = (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
               f'<div><div style="font-size:11px;color:{_C["muted"]};text-transform:uppercase">Points forts</div>'
               f'<ul style="margin:6px 0 0;padding-left:16px">{st}</ul></div>'
               f'<div><div style="font-size:11px;color:{_C["muted"]};text-transform:uppercase">Points de vigilance</div>'
               f'<ul style="margin:6px 0 0;padding-left:16px">{wt}</ul></div></div>')

    # Résultats & estimations (forte valeur)
    earn_card = ""
    e = r.get("earnings")
    if e:
        def _sur(est, act):
            if est and act and est != 0:
                d = (act / est - 1) * 100
                return f' <span style="color:{_C["pos"] if d>=0 else _C["neg"]}">({d:+.0f}%)</span>'
            return ""
        earn_card = _card("Résultats & estimations analystes", _kv_grid([
            ("Prochain résultat", e.get("next_date") or "—", _C["accent"]),
            ("BPA estimé", _num(e.get("eps_estimate")), _C["fg"]),
            ("BPA annoncé", (_num(e.get("eps_actual")) + _sur(e.get("eps_estimate"), e.get("eps_actual"))) if e.get("eps_actual") is not None else "—", _C["fg"]),
            ("Revenu estimé", _money(e.get("revenue_estimate")), _C["fg"]),
            ("Revenu annoncé", _money(e.get("revenue_actual")) if e.get("revenue_actual") is not None else "—", _C["fg"]),
        ]))

    # Technique (si pertinente)
    tech_card = ""
    t = r.get("technical")
    if t:
        tcol = {"haussière": _C["pos"], "baissière": _C["neg"]}.get(str(t.get("trend")), _C["fg"])
        tech_card = _card("Analyse technique", _kv_grid([
            ("Tendance", str(t.get("trend") or "—"), tcol),
            ("RSI (14)", _num(t.get("rsi"), 0), _C["fg"]),
            ("MACD", str(t.get("macd_signal") or "—"), _C["fg"]),
            ("vs MM50", _pct(t.get("vs_sma50")), _C["fg"]),
            ("vs MM200", _pct(t.get("vs_sma200")), _C["fg"]),
            ("Plage 52 sem.", f'${_num(t.get("low_52w"),0)} – ${_num(t.get("high_52w"),0)}', _C["muted"]),
        ]))

    # Macro & régime (top-down)
    macro_card = ""
    mc = r.get("macro")
    if mc:
        macro_card = _card("Contexte macroéconomique", _kv_grid([
            ("Régime de marché", str(mc.get("regime") or "—"), _C["fg"]),
            ("VIX", _num(mc.get("vix"), 1), _C["fg"]),
            ("Exposition conseillée", _pct(mc.get("exposure")) if mc.get("exposure") is not None else "—", _C["fg"]),
            ("Taux 10 ans", _pct(mc.get("rate_10y")) if mc.get("rate_10y") is not None else "—", _C["fg"]),
        ]))

    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Note d'analyse — {idy['name']} ({idy['symbol']})</title>
<style>@media print{{body{{background:#fff!important;color:#000!important}}}}</style></head>
<body style="margin:0;background:{_C['bg']};color:{_C['fg']};
font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Inter,system-ui,sans-serif;line-height:1.45">
<div style="max-width:860px;margin:0 auto;padding:28px 24px">
<div style="font-size:11px;color:{_C['muted']};letter-spacing:.08em;text-transform:uppercase;margin-bottom:6px">
Note d'analyse fondamentale · {r['as_of']}</div>
{header}
{_card("Audit d'intégrité des données (PwC)", _findings_html(audit))}
{_card("Analyse économique (Vernimmen)", vern)}
{_card("Valorisation (Damodaran)", dam_kv)}
{earn_card}
{_card("Qualité & solidité", qual)}
{tech_card}
{macro_card}
{_card("Synthèse — piliers de notation", pillars)}
{_card("Verdict", verdict)}
<p style="font-size:10px;color:{_C['muted']};margin-top:18px">
Sources gratuites (Yahoo Finance / FMP / SEC EDGAR — 10-K, 10-Q) + recalculs internes audités.
Cadre Vernimmen (rentabilité économique) & A. Damodaran (coût du capital, DCF). Ce document est
une aide à la décision, pas un conseil en investissement.</p>
</div></body></html>"""


def company_report_pdf(r: dict[str, Any], out_path: str | Path) -> Path | None:
    """PDF via reportlab si présent ; sinon écrit le HTML (imprimable) et renvoie None pour le PDF.
    Best-effort : ne lève jamais pour ne pas casser un pipeline."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas
    except Exception:  # noqa: BLE001 — pas de reportlab → repli HTML
        html_path = out.with_suffix(".html")
        html_path.write_text(company_report_html(r), encoding="utf-8")
        return None
    idy, sc, ver, dam = r["identity"], r["score"], r["vernimmen"], r["damodaran"]
    c = canvas.Canvas(str(out), pagesize=A4)
    w, h = A4
    y = h - 2 * cm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, f"Note d'analyse — {idy['name']} ({idy['symbol']})")
    c.setFont("Helvetica", 10); y -= 0.7 * cm
    c.drawString(2 * cm, y, f"{idy['sector']} · score {sc['global']}/100 · {sc['recommendation']}")
    lines = [
        ("ROCE après impôt", _pct(ver.get("roce_after_tax"))),
        ("WACC", _pct(ver.get("wacc"))),
        ("Spread ROCE-WACC", _pct(ver.get("value_creation_spread")) if ver.get("value_creation_spread") is not None else "—"),
        ("EVA", _money(ver.get("eva"))),
        ("DCF base / marge de sécurité", f"${_num(dam['dcf'].get('scenarios',{}).get('base'))} / "
         f"{_pct(dam['dcf'].get('margin_of_safety')) if dam['dcf'].get('margin_of_safety') is not None else '—'}"),
        ("Piotroski / Altman Z", f"{r['quality']['piotroski_f_score']}/9 · "
         f"{r['quality']['altman_z'].get('z')}"),
    ]
    c.setFont("Helvetica", 11); y -= 1.0 * cm
    for k, val in lines:
        c.drawString(2 * cm, y, str(k)); c.drawRightString(w - 2 * cm, y, str(val)); y -= 0.7 * cm
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(2 * cm, 1.5 * cm, "Sources gratuites auditées (PwC) · Vernimmen & Damodaran · pas un conseil.")
    c.showPage(); c.save()
    return out
