"""Rendu de la note d'analyse — HTML autonome (toujours) + PDF (reportlab si présent).

Design « Apple-quality » : sobre, dense, hiérarchie claire, typographie système, jauges SVG.
HTML imprimable (Ctrl-P → PDF) partout, même sans reportlab. Aucune dépendance dure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_C = {"bg": "#0b0d10", "card": "#14171b", "card2": "#1a1e24", "border": "#262b33",
      "fg": "#e8eaed", "muted": "#9aa1ab", "accent": "#22d3ee", "pos": "#22c55e",
      "warn": "#f59e0b", "neg": "#ef4444", "blue": "#3b82f6"}


def _fr_date(iso: str | None) -> str:
    """ISO AAAA-MM-JJ → JJ/MM/AAAA (date de génération du rapport)."""
    s = str(iso or "")
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s


def _isnan(x) -> bool:
    return isinstance(x, float) and x != x


def _pct(x: float | None, nd: int = 1) -> str:
    return "—" if (x is None or _isnan(x)) else f"{x*100:.{nd}f}%"


def _num(x: float | None, nd: int = 2) -> str:
    return "—" if (x is None or _isnan(x)) else f"{x:,.{nd}f}".replace(",", " ")


def _money(x: float | None) -> str:
    if x is None or _isnan(x):
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


def _poly(vals: list[float], w: float, h: float, pad: float = 4) -> str:
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals)
    return " ".join(f"{pad+i*(w-2*pad)/(n-1):.1f},{h-pad-(v-lo)/rng*(h-2*pad):.1f}"
                    for i, v in enumerate(vals))


_PADL = 52      # marge gauche pour les labels d'axe Y
_PADB = 18      # marge basse pour les labels d'axe X


def _money_axis(v: float) -> str:
    if v is None or _isnan(v):
        return "—"
    a = abs(v)
    for div, suf in ((1e12, "T"), (1e9, "Md"), (1e6, "M"), (1e3, "k")):
        if a >= div:
            return f"{v/div:.1f}{suf}"
    return f"{v:.0f}"


def _poly_xy(vals: list[float], lo: float, hi: float, x0: float, x1: float, y0: float, y1: float) -> str:
    rng = (hi - lo) or 1.0
    n = len(vals)
    return " ".join(f"{x0+i*(x1-x0)/(n-1):.1f},{y1-(v-lo)/rng*(y1-y0):.1f}" for i, v in enumerate(vals))


def _spark_price(closes: list[float], labels: list[str] | None = None, w: int = 760, h: int = 150) -> str:
    """Cours + MM50/200 avec AXES CHIFFRÉS (Y = prix $, X = dates). Aire douce + grille."""
    if len(closes) < 20:
        return ""
    def _ma(n: int) -> list[float]:
        return [sum(closes[max(0, i-n+1):i+1]) / min(i+1, n) for i in range(len(closes))]
    lo, hi = min(closes), max(closes)
    x0, x1, y0, y1 = _PADL, w - 6, 8, h - _PADB
    grid, ylab = "", ""
    for k in range(5):                                   # 5 lignes de grille + valeurs $ sur Y
        yy = y0 + (y1 - y0) * k / 4
        val = hi - (hi - lo) * k / 4
        grid += f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" stroke="{_C["border"]}" stroke-width="0.5"/>'
        ylab += f'<text x="{x0-6}" y="{yy+3:.1f}" text-anchor="end" font-size="9" fill="{_C["muted"]}">${_num(val,0)}</text>'
    price = _poly_xy(closes, lo, hi, x0, x1, y0, y1)
    area = f"{price} {x1:.1f},{y1:.1f} {x0:.1f},{y1:.1f}"
    layers = (f'<polygon points="{area}" fill="{_C["accent"]}" opacity="0.08"/>'
              f'<polyline points="{price}" fill="none" stroke="{_C["accent"]}" stroke-width="1.8"/>')
    if len(closes) >= 50:
        layers += f'<polyline points="{_poly_xy(_ma(50), lo, hi, x0, x1, y0, y1)}" fill="none" stroke="{_C["warn"]}" stroke-width="1" opacity="0.85"/>'
    if len(closes) >= 200:
        layers += f'<polyline points="{_poly_xy(_ma(200), lo, hi, x0, x1, y0, y1)}" fill="none" stroke="{_C["muted"]}" stroke-width="1" opacity="0.7"/>'
    xlab = ""
    if labels and len(labels) >= 2:                      # dates début/milieu/fin sur X
        for frac, anc in ((0.0, "start"), (0.5, "middle"), (1.0, "end")):
            idx = min(len(labels) - 1, int(frac * (len(labels) - 1)))
            xx = x0 + (x1 - x0) * frac
            xlab += f'<text x="{xx:.1f}" y="{h-5}" text-anchor="{anc}" font-size="9" fill="{_C["muted"]}">{labels[idx]}</text>'
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}">{grid}{layers}{ylab}{xlab}</svg>'


def _spark_drawdown(closes: list[float], labels: list[str] | None = None, w: int = 760, h: int = 90) -> str:
    """Drawdown (sous l'eau) avec axe Y en % et repères de dates."""
    if len(closes) < 20:
        return ""
    peak, dd = closes[0], []
    for c in closes:
        peak = max(peak, c)
        dd.append(c / peak - 1.0 if peak else 0.0)
    lo = min(dd); hi = 0.0
    x0, x1, y0, y1 = _PADL, w - 6, 8, h - _PADB
    grid = ylab = ""
    for k in range(3):
        yy = y0 + (y1 - y0) * k / 2
        val = hi - (hi - lo) * k / 2
        grid += f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" stroke="{_C["border"]}" stroke-width="0.5"/>'
        ylab += f'<text x="{x0-6}" y="{yy+3:.1f}" text-anchor="end" font-size="9" fill="{_C["muted"]}">{val*100:.0f}%</text>'
    pts = _poly_xy(dd, lo, hi, x0, x1, y0, y1)
    area = f"{pts} {x1:.1f},{y0:.1f} {x0:.1f},{y0:.1f}"
    xlab = ""
    if labels and len(labels) >= 2:
        for frac, anc in ((0.0, "start"), (1.0, "end")):
            idx = min(len(labels) - 1, int(frac * (len(labels) - 1)))
            xx = x0 + (x1 - x0) * frac
            xlab += f'<text x="{xx:.1f}" y="{h-5}" text-anchor="{anc}" font-size="9" fill="{_C["muted"]}">{labels[idx]}</text>'
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}">{grid}'
            f'<polygon points="{area}" fill="{_C["neg"]}" opacity="0.12"/>'
            f'<polyline points="{pts}" fill="none" stroke="{_C["neg"]}" stroke-width="1.4"/>{ylab}{xlab}</svg>')


def _bars_history(hist: list[dict], key: str, w: int = 760, h: int = 150) -> str:
    """Barres annuelles (CA/résultat) avec VALEUR au-dessus de chaque barre, année en X, axe Y."""
    vals = [float(x.get(key) or 0) for x in hist]
    if len(vals) < 2:
        return ""
    hi = max(vals + [0.0]); lo = min(vals + [0.0])
    span = (hi - lo) or 1.0
    x0, y0, y1 = _PADL, 14, h - _PADB
    plot_w = w - x0 - 6
    zero_y = y1 - (0 - lo) / span * (y1 - y0)            # ligne du zéro
    n = len(vals)
    gap = plot_w / n
    bw = gap * 0.6
    grid = (f'<line x1="{x0}" y1="{zero_y:.1f}" x2="{w-6}" y2="{zero_y:.1f}" stroke="{_C["border"]}" stroke-width="0.6"/>'
            f'<text x="{x0-6}" y="{y0+3}" text-anchor="end" font-size="9" fill="{_C["muted"]}">{_money_axis(hi)}</text>'
            f'<text x="{x0-6}" y="{zero_y+3:.1f}" text-anchor="end" font-size="9" fill="{_C["muted"]}">0</text>')
    bars = ""
    for i, (x, v) in enumerate(zip(hist, vals)):
        cx = x0 + i * gap + (gap - bw) / 2
        vy = y1 - (v - lo) / span * (y1 - y0)
        top = min(vy, zero_y); bh = abs(vy - zero_y)
        col = _C["accent"] if v >= 0 else _C["neg"]
        ly = (top - 3) if v >= 0 else (max(vy, zero_y) + 10)   # libellé au-dessus si positif, en-dessous si négatif
        bars += (f'<rect x="{cx:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(1,bh):.1f}" rx="2" fill="{col}" opacity="0.85"/>'
                 f'<text x="{cx+bw/2:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="9" fill="{_C["fg"]}">{_money_axis(v)}</text>'
                 f'<text x="{cx+bw/2:.1f}" y="{h-5}" text-anchor="middle" font-size="9" fill="{_C["muted"]}">{x.get("year","")}</text>')
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}">{grid}{bars}</svg>'


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


def _apply_theme(html: str, theme: str) -> str:
    """Bascule la palette sombre→claire par remplacement de tokens (sans mutation globale, thread-safe)."""
    if theme != "light":
        return html
    tmp = [("#0b0d10", "@BG@"), ("#14171b", "@CARD@"), ("#1a1e24", "@CARD2@"),
           ("#262b33", "@BORDER@"), ("#e8eaed", "@FG@"), ("#9aa1ab", "@MUTED@")]
    for a, t in tmp:
        html = html.replace(a, t)
    light = {"@BG@": "#ffffff", "@CARD@": "#f7f8fa", "@CARD2@": "#eef2f6",
             "@BORDER@": "#e3e7ec", "@FG@": "#0b0d10", "@MUTED@": "#5b6470"}
    for t, c in light.items():
        html = html.replace(t, c)
    return html


def _snowflake_svg(axes: dict, size: int = 260) -> str:
    """Radar « Portfolio Snowflake » (5 axes) — design Apple : dégradé doux, anneaux subtils, sommets
    marqués, labels + valeurs nettes. SVG autonome."""
    import math
    labels = ["VALUE", "FUTURE", "PAST", "HEALTH", "DIVIDEND"]
    cx = cy = size / 2
    R = size / 2 - 42                                      # marge pour les labels
    gold, gold2 = "#f0c020", "#caa00f"
    n = len(labels)
    def _pt(i, rad):
        a = -math.pi / 2 + i * 2 * math.pi / n
        return cx + rad * math.cos(a), cy + rad * math.sin(a)
    rings = ""
    for k in (0.25, 0.5, 0.75, 1.0):                      # anneaux très subtils
        pts = " ".join(f"{_pt(i, R*k)[0]:.1f},{_pt(i, R*k)[1]:.1f}" for i in range(n))
        rings += f'<polygon points="{pts}" fill="none" stroke="{_C["border"]}" stroke-width="0.7" opacity="0.6"/>'
    spokes = lab = dots = ""
    for i, name in enumerate(labels):
        ex, ey = _pt(i, R)
        spokes += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{_C["border"]}" stroke-width="0.6" opacity="0.6"/>'
        lx, ly = _pt(i, R + 18)
        anchor = "middle" if abs(lx - cx) < 6 else ("start" if lx > cx else "end")
        lab += (f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="9.5" '
                f'fill="{_C["muted"]}" letter-spacing="1.2" font-weight="600">{name}</text>'
                f'<text x="{lx:.1f}" y="{ly+12:.1f}" text-anchor="{anchor}" font-size="10" '
                f'fill="{_C["fg"]}" font-weight="700">{axes.get(name,0)}</text>')
    pts_xy = [_pt(i, R * max(0.05, axes.get(labels[i], 0) / 100)) for i in range(n)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts_xy)
    for x, y in pts_xy:
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="{gold}"/>'
    grad = (f'<defs><radialGradient id="sf" cx="50%" cy="50%" r="65%">'
            f'<stop offset="0%" stop-color="{gold}" stop-opacity="0.92"/>'
            f'<stop offset="100%" stop-color="{gold2}" stop-opacity="0.62"/></radialGradient></defs>')
    return (f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">{grad}{rings}{spokes}'
            f'<polygon points="{poly}" fill="url(#sf)" stroke="{gold}" stroke-width="1.8" '
            f'stroke-linejoin="round"/>{dots}{lab}</svg>')


def _holders_bars(rows: list[dict], key: str, pct: bool) -> str:
    """Barres horizontales Apple-grade pour l'actionnariat (plus lisible qu'un camembert)."""
    vals = [(_x.get("name") or "—", _x.get(key)) for _x in rows if _x.get(key) is not None]
    if not vals:
        return f'<div style="font-size:11px;color:{_C["muted"]}">données indisponibles</div>'
    mx = max(v for _, v in vals) or 1.0
    out = ""
    for name, v in vals:
        wpct = max(3, round(v / mx * 100))
        label = (f"{v*100:.1f}%" if pct else _money_axis(v))
        out += (f'<div style="margin:5px 0">'
                f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:2px">'
                f'<span style="color:{_C["fg"]}">{_trunc(name, 26)}</span>'
                f'<span style="color:{_C["muted"]};font-variant-numeric:tabular-nums">{label}</span></div>'
                f'<div style="height:6px;border-radius:3px;background:{_C["border"]}">'
                f'<div style="height:6px;border-radius:3px;width:{wpct}%;background:{_C["accent"]}"></div></div></div>')
    return out


def _reconciliation_html(r: dict[str, Any]) -> str:
    """Carte « Réconciliation GAAP vs Non-GAAP » — CA & résultat net : reporté vs SEC EDGAR (GAAP)."""
    rec = r.get("reconciliation")
    if not rec or not rec.get("rows"):
        return ""
    def _b(x):
        return _money(x) if x is not None else "—"
    rows = ""
    for x in rec["rows"]:
        col = _C["pos"] if x["status"] == "réconcilié" else _C["warn"] if x["status"] == "écart majeur" else _C["neg"]
        rows += (f'<tr style="border-top:1px solid {_C["border"]}">'
                 f'<td style="padding:5px 0">{x["metric"]}</td>'
                 f'<td style="text-align:right">{_b(x["reported"])}</td>'
                 f'<td style="text-align:right">{_b(x["gaap"])}</td>'
                 f'<td style="text-align:right;color:{col}">{x["gap"]*100:.0f}%</td>'
                 f'<td style="text-align:right;color:{col}">{x["status"]}</td></tr>')
    inner = (f'<table style="width:100%;font-size:12px"><thead><tr style="color:{_C["muted"]};font-size:11px">'
             f'<th style="text-align:left">Métrique</th><th style="text-align:right">Reporté (non-GAAP)</th>'
             f'<th style="text-align:right">GAAP (SEC)</th><th style="text-align:right">Écart</th>'
             f'<th style="text-align:right">Statut</th></tr></thead><tbody>{rows}</tbody></table>'
             f'<p style="font-size:10px;color:{_C["muted"]};margin:8px 0 0">{rec.get("note","")}</p>')
    return _card("Réconciliation GAAP vs Non-GAAP", inner)


def company_report_html(r: dict[str, Any], theme: str = "dark") -> str:
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

    # en-tête — Hero Section (ticker/capi/prix massifs, badge statut faible saturation)
    status = sc.get("verdict_status", sc["recommendation"].upper())
    blocking = (r.get("flags") or {}).get("blocking_alert")
    badge_col = _C["neg"] if blocking else _tone(g)
    _name = idy.get("name") or ""
    name_line = (f'<div style="color:{_C["muted"]};font-size:14px;font-weight:500;margin-top:1px">{_name}</div>'
                 if (_name and _name != idy["symbol"]) else "")
    header = (
        f'<div style="display:flex;align-items:center;gap:22px;margin-bottom:16px">'
        f'<div>{_gauge(g)}</div>'
        f'<div style="flex:1">'
        f'<div style="font-size:30px;font-weight:800;letter-spacing:-.01em">{idy["symbol"]}</div>{name_line}'
        f'<div style="color:{_C["muted"]};font-size:14px;margin-top:2px">{idy["sector"]} · '
        f'<b style="color:{_C["fg"]}">{_money(idy["market_cap"])}</b> · cours <b style="color:{_C["fg"]}">${_num(idy["price"])}</b></div>'
        f'<div style="margin-top:8px;display:inline-block;padding:4px 14px;border-radius:999px;'
        f'background:{badge_col}1f;color:{badge_col};font-weight:700;font-size:13px;letter-spacing:.02em">'
        f'{status} · {g}/100</div>'
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
    reliable = dcf.get("reliable", True)
    if not reliable:
        # valorisation masquée : comptes en devise locale ≠ cours (ADR) → on N'AFFICHE PAS de faux chiffres
        dam_kv = (f'<div style="background:{_C["warn"]}22;border-left:3px solid {_C["warn"]};'
                  f'border-radius:8px;padding:10px 12px;font-size:12px;color:{_C["fg"]}">'
                  f'⚠️ <b>Valorisation non fiable</b> — les comptes semblent publiés dans une devise '
                  f'différente du cours (titre type ADR). DCF & multiples masqués pour ne pas induire '
                  f'en erreur. Coût du capital indicatif : MEDAF {_pct(dam.get("cost_of_equity"))} · '
                  f'WACC {_pct(dam.get("wacc"))} · bêta {_num(dam.get("beta"))}.</div>')
    else:
        _base = scen.get("base")
        _dcf_ok = _base is not None and not _isnan(_base)
        rows = [("Coût des FP (MEDAF)", _pct(dam.get("cost_of_equity")), _C["fg"]),
                ("WACC", _pct(dam.get("wacc")), _C["fg"]),
                ("Bêta", _num(dam.get("beta")), _C["fg"])]
        if _dcf_ok:
            rows += [("DCF bear", "$" + _num(scen.get("bear")), _C["muted"]),
                     ("DCF base", "$" + _num(scen.get("base")), _C["fg"]),
                     ("DCF bull", "$" + _num(scen.get("bull")), _C["muted"]),
                     ("Marge de sécurité", _pct(mos) if mos is not None else "—",
                      _C["pos"] if (mos or 0) > 0 else _C["neg"]),
                     ("Croiss. implicite (cours)", _pct(dam.get("implied_growth_in_price")), _C["fg"])]
        else:
            rows.append(("DCF (FCFF)", "non calculable (FCF négatif)", _C["muted"]))
        dam_kv = _kv_grid(rows)
        # multiples de valorisation (toujours affichés quand fiables)
        mu = dam.get("multiples", {})
        dam_kv += (f'<div style="margin-top:12px;font-size:12px;color:{_C["muted"]}">Multiples : '
                   f'P/E <b style="color:{_C["fg"]}">{_num(mu.get("pe"),1)}</b> · '
                   f'EV/EBITDA <b style="color:{_C["fg"]}">{_num(mu.get("ev_ebitda"),1)}</b> · '
                   f'EV/Sales <b style="color:{_C["fg"]}">{_num(mu.get("ev_sales"),1)}</b> · '
                   f'P/B <b style="color:{_C["fg"]}">{_num(mu.get("price_to_book"),1)}</b> · '
                   f'rdt FCF <b style="color:{_C["fg"]}">{_pct(mu.get("fcf_yield"))}</b> · '
                   f'rdt bénéf. <b style="color:{_C["fg"]}">{_pct(mu.get("earnings_yield"))}</b></div>')
    # multiples vs secteur
    mvs = dam.get("multiples_vs_sector", {})
    if mvs and reliable:
        rows = "".join(
            f'<tr style="border-top:1px solid {_C["border"]}"><td style="padding:4px 0">{k.upper()}</td>'
            f'<td style="text-align:right">{_num(v.get("company"))}</td>'
            f'<td style="text-align:right;color:{_C["muted"]}">{_num(v.get("sector"))}</td></tr>'
            for k, v in mvs.items())
        dam_kv += (f'<table style="width:100%;font-size:12px;margin-top:12px"><thead>'
                   f'<tr style="color:{_C["muted"]}"><th style="text-align:left">Multiple</th>'
                   f'<th style="text-align:right">Société</th><th style="text-align:right">Secteur</th></tr>'
                   f'</thead><tbody>{rows}</tbody></table>')

    # Positionnement sectoriel (vs pairs)
    sector_card = ""
    scmp = r.get("sector_comparison") or {}
    if scmp.get("available") and scmp.get("rows"):
        def _fmt(metric, val):
            return _pct(val) if metric in ("net_margin", "roe", "roic", "gross_margin", "revenue_growth") else _num(val)
        rows = "".join(
            f'<tr style="border-top:1px solid {_C["border"]}">'
            f'<td style="padding:5px 0">{x["label"]}</td>'
            f'<td style="text-align:right">{_fmt(x["metric"], x["company"])}</td>'
            f'<td style="text-align:right;color:{_C["muted"]}">{_fmt(x["metric"], x["sector_median"])}</td>'
            f'<td style="text-align:right">{int(x["percentile"]*100)}<span style="font-size:9px;color:{_C["muted"]}">e</span></td>'
            f'<td style="text-align:right;color:{_C["pos"] if x["verdict"]=="favorable" else _C["neg"]}">{x["verdict"]}</td></tr>'
            for x in scmp["rows"])
        sector_card = _card(
            f'Positionnement sectoriel ({scmp.get("favorable",0)}/{scmp.get("total",0)} favorables · {scmp.get("n_peers",0)} pairs)',
            f'<table style="width:100%;font-size:12px"><thead><tr style="color:{_C["muted"]};font-size:11px">'
            f'<th style="text-align:left">Métrique</th><th style="text-align:right">Société</th>'
            f'<th style="text-align:right">Médiane sect.</th><th style="text-align:right">Rang</th>'
            f'<th style="text-align:right">Verdict</th></tr></thead><tbody>{rows}</tbody></table>')

    # Qualité
    z = ql["altman_z"]; inv = ql["investor_scores"]
    qual = _kv_grid([
        ("Piotroski F-score", f'{ql["piotroski_f_score"]}/9 ({ql["piotroski_label"]})', _C["fg"]),
        ("Altman Z", (f'{z.get("z")} ({z.get("zone")})' if z.get("z") is not None else "N/A"), _C["fg"]),
        ("Graham", f'{inv.get("graham")}/100', _C["fg"]),
        ("Fisher", f'{inv.get("fisher")}/100', _C["fg"]),
        ("Thiel", f'{inv.get("thiel")}/100', _C["fg"]),
    ])

    # Synthèse Advisory Board — Moat / Tail Risk
    v = r["verdict"]
    st = "".join(f'<li style="color:{_C["pos"]};font-size:12px;margin:3px 0">✓ {s}</li>' for s in v["strengths"])
    wt = "".join(f'<li style="color:{_C["warn"]};font-size:12px;margin:3px 0">▸ {s}</li>' for s in v["watch"])
    if (r.get("flags") or {}).get("blocking_alert"):
        wt = (f'<li style="color:{_C["neg"]};font-size:12px;margin:3px 0;font-weight:600">⛔ Réconciliation '
              f'de données requise — ne pas trader avant résolution.</li>') + wt
    _lab = "font-size:9px;letter-spacing:.14em;text-transform:uppercase"
    verdict = (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
               f'<div><div style="color:{_C["muted"]};{_lab}">Points forts · Moat</div>'
               f'<ul style="margin:6px 0 0;padding-left:16px">{st}</ul></div>'
               f'<div><div style="color:{_C["muted"]};{_lab}">Risques fatals · Tail Risk</div>'
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

    # Graphiques (cours+MM, drawdown, barres CA/résultat)
    charts_card = ""
    ch = r.get("charts") or {}
    closes = ch.get("price") or []
    labels = ch.get("price_labels") or []
    hist = ch.get("financial_history") or []
    inner = ""
    if len(closes) >= 20:
        last = closes[-1]; lo = min(closes); hi = max(closes)
        period = f" · période {labels[0]} → {labels[-1]}" if len(labels) >= 2 else ""
        inner += (f'<div style="font-size:11px;color:{_C["muted"]};margin-bottom:2px">Cours & moyennes mobiles '
                  f'(<span style="color:{_C["accent"]}">cours ${_num(last)}</span> · '
                  f'<span style="color:{_C["warn"]}">MM50</span> · <span style="color:{_C["muted"]}">MM200</span>'
                  f' · plage ${_num(lo,0)}–${_num(hi,0)}{period})</div>{_spark_price(closes, labels)}')
        inner += (f'<div style="font-size:11px;color:{_C["muted"]};margin:8px 0 2px">Drawdown (sous l\'eau)</div>'
                  f'{_spark_drawdown(closes, labels)}')
    if len(hist) >= 2:
        cagr = ch.get("revenue_cagr")
        cagr_txt = (f' <span style="color:{_C["pos"] if cagr>=0 else _C["neg"]}">· CAGR {cagr*100:+.1f}%</span>'
                    if cagr is not None else "")
        ny = ch.get("history_years") or len(hist)
        inner += (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:8px">'
                  f'<div><div style="font-size:11px;color:{_C["muted"]};margin-bottom:2px">Chiffre d\'affaires '
                  f'({ny} ex.){cagr_txt}</div>{_bars_history(hist, "revenue")}</div>'
                  f'<div><div style="font-size:11px;color:{_C["muted"]};margin-bottom:2px">Résultat net</div>'
                  f'{_bars_history(hist, "net_income")}</div></div>')
    if inner:
        charts_card = _card("Graphiques", inner)

    # Données financières — tableau chiffré par exercice (fort impact)
    findata_card = ""
    if len(hist) >= 2:
        rows = ""
        for x in hist:
            rev = x.get("revenue"); ni = x.get("net_income"); eps = x.get("eps")
            nm = (ni / rev) if (rev and ni is not None and rev != 0) else None
            rows += (f'<tr style="border-top:1px solid {_C["border"]}">'
                     f'<td style="padding:4px 0">{x.get("year","—")}</td>'
                     f'<td style="text-align:right">{_money(rev)}</td>'
                     f'<td style="text-align:right">{_money(ni)}</td>'
                     f'<td style="text-align:right;color:{_C["muted"]}">{_num(eps) if eps is not None else "—"}</td>'
                     f'<td style="text-align:right;color:{(_C["pos"] if (nm or 0)>=0 else _C["neg"])}">{_pct(nm) if nm is not None else "—"}</td></tr>')
        findata_card = _card("Données financières (par exercice)",
            f'<table style="width:100%;font-size:12px"><thead><tr style="color:{_C["muted"]};font-size:11px">'
            f'<th style="text-align:left">Exercice</th><th style="text-align:right">CA</th>'
            f'<th style="text-align:right">Résultat net</th><th style="text-align:right">BPA</th>'
            f'<th style="text-align:right">Marge nette</th></tr></thead><tbody>{rows}</tbody></table>')

    # Données financières — TRIMESTRES (récents)
    quarterly_card = ""
    qd = r.get("quarterly") or []
    if len(qd) >= 2:
        qrows = ""
        for x in qd:
            rev = x.get("revenue"); ni = x.get("net_income"); eps = x.get("eps"); nm = x.get("net_margin")
            qrows += (f'<tr style="border-top:1px solid {_C["border"]}">'
                      f'<td style="padding:4px 0">{x.get("period","—")}</td>'
                      f'<td style="text-align:right">{_money(rev)}</td>'
                      f'<td style="text-align:right">{_money(ni)}</td>'
                      f'<td style="text-align:right;color:{_C["muted"]}">{_num(eps) if eps is not None else "—"}</td>'
                      f'<td style="text-align:right;color:{(_C["pos"] if (nm or 0)>=0 else _C["neg"])}">{_pct(nm) if nm is not None else "—"}</td></tr>')
        quarterly_card = _card("Données financières (par trimestre)",
            f'<table style="width:100%;font-size:12px"><thead><tr style="color:{_C["muted"]};font-size:11px">'
            f'<th style="text-align:left">Trimestre</th><th style="text-align:right">CA</th>'
            f'<th style="text-align:right">Résultat net</th><th style="text-align:right">BPA</th>'
            f'<th style="text-align:right">Marge nette</th></tr></thead><tbody>{qrows}</tbody></table>')

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

    # Portfolio Snowflake (radar 5 axes)
    snow_card = ""
    snow = r.get("snowflake") or {}
    if snow.get("axes"):
        ax = snow["axes"]
        _dy = r.get("dividend_yield")
        _extra = {"DIVIDEND": (f" · rdt {_pct(_dy)}" if _dy else " · non-payeur")}
        legend = "".join(
            f'<div style="display:flex;justify-content:space-between;font-size:11px;margin:3px 0">'
            f'<span style="color:{_C["muted"]};letter-spacing:.08em">{k}{_extra.get(k,"")}</span>'
            f'<span style="color:{_C["fg"]};font-variant-numeric:tabular-nums">{v}/100</span></div>'
            for k, v in ax.items())
        snow_card = _card("Portfolio Snowflake", (
            f'<div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">'
            f'<div>{_snowflake_svg(ax)}</div>'
            f'<div style="flex:1;min-width:160px">{legend}'
            f'<div style="margin-top:8px;font-size:12px;color:{_C["muted"]};font-style:italic">{snow.get("summary","")}</div>'
            f'</div></div>'))

    # Risk management de l'actif
    risk_card = ""
    rk = r.get("risk") or {}
    if rk.get("available"):
        risk_card = _card("Risk management de l'actif", _kv_grid([
            ("Volatilité annualisée", _pct(rk.get("vol_annual")), _C["fg"]),
            ("Max drawdown", _pct(rk.get("max_drawdown")), _C["neg"]),
            ("VaR 95 % (1j)", _pct(rk.get("var_95")), _C["neg"]),
            ("CVaR 95 % (1j)", _pct(rk.get("cvar_95")), _C["neg"]),
            ("Sharpe / Sortino", f'{_num(rk.get("sharpe"))} / {_num(rk.get("sortino"))}', _C["fg"]),
            ("Bêta marché", _num(rk.get("beta")) if rk.get("beta") is not None else "—", _C["fg"]),
            ("Stop suggéré (~2σ hebdo)", _pct(rk.get("suggested_stop")), _C["warn"]),
        ]))

    # Actionnariat — top 5 institutionnels + insiders (barres horizontales)
    holders_card = ""
    hd = r.get("holders") or {}
    inst = hd.get("institutional") or []; insi = hd.get("insiders") or []
    if inst or insi:
        cols = ""
        if inst:
            cols += (f'<div><div style="font-size:11px;color:{_C["muted"]};margin-bottom:6px">'
                     f'Top institutionnels (% du capital)</div>{_holders_bars(inst, "pct", pct=True)}</div>')
        if insi:
            _ik = "pct" if any(x.get("pct") is not None for x in insi) else "shares"
            cols += (f'<div><div style="font-size:11px;color:{_C["muted"]};margin-bottom:6px">'
                     f'Top insiders (% du capital)</div>{_holders_bars(insi, _ik, pct=(_ik=="pct"))}</div>')
        holders_card = _card("Actionnariat — répartition", f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">{cols}</div>')

    blocking_html = ""
    if (r.get("flags") or {}).get("blocking_alert"):
        blocking_html = (
            f'<div style="background:{_C["neg"]}1f;border:1px solid {_C["neg"]};border-radius:10px;'
            f'padding:11px 14px;margin-bottom:14px;font-size:13px;color:{_C["neg"]};font-weight:600">'
            "⛔ CONTRÔLE REQUIS — réconciliation de données nécessaire (écart inter-sources). "
            "Ordre gelé (paper/live) jusqu'à résolution.</div>")
    memo_html = ""
    if r.get("memo"):
        _src = " · IA" if r.get("memo_source") == "IA locale" else ""
        memo_html = (
            f'<div style="background:{_C["card2"]};border-left:3px solid {_C["accent"]};border-radius:10px;'
            f'padding:12px 14px;margin-bottom:14px;font-size:13px;color:{_C["fg"]}">'
            f'<span style="font-size:9px;color:{_C["muted"]};text-transform:uppercase;letter-spacing:.14em">'
            f'Axe directeur{_src}</span>'
            f'<div style="margin-top:5px;line-height:1.5">{r["memo"]}</div></div>')
    fx_html = ""
    if r.get("fx_conversion"):
        fx_html = (f'<div style="font-size:11px;color:{_C["muted"]};margin:-6px 0 12px">💱 '
                   f'{r["fx_conversion"]} — valorisation calculée après conversion de devise.</div>')
    _html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Note d'analyse — {idy['name']} ({idy['symbol']})</title>
<style>@media print{{body{{background:#fff!important;color:#000!important}}}}</style></head>
<body style="margin:0;background:{_C['bg']};color:{_C['fg']};
font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Inter,system-ui,sans-serif;line-height:1.45">
<div style="max-width:860px;margin:0 auto;padding:28px 24px">
<div style="font-size:10px;color:{_C['muted']};letter-spacing:.14em;text-transform:uppercase;margin-bottom:8px">
Rapport effectué le {_fr_date(r['as_of'])}</div>
{header}
{blocking_html}
{memo_html}
{fx_html}
{snow_card}
{_card("Synthèse — piliers de notation", pillars)}
{_card("Audit d'intégrité des données", _findings_html(audit))}
{_reconciliation_html(r)}
{_card("Valorisation (Damodaran)", dam_kv)}
{_card("Analyse économique (Vernimmen)", vern)}
{charts_card}
{findata_card}
{quarterly_card}
{sector_card}
{_card("Qualité & solidité", qual)}
{risk_card}
{tech_card}
{macro_card}
{earn_card}
{holders_card}
{_card("Synthèse Advisory Board — Moat & Tail Risk", verdict)}
<p style="font-size:10px;color:{_C['muted']};margin-top:18px">
Sources gratuites (Yahoo Finance / FMP / SEC EDGAR — 10-K, 10-Q) + recalculs internes contrôlés.
Cadre Vernimmen (rentabilité économique) & A. Damodaran (coût du capital, DCF). Ce document est
une aide à la décision, pas un conseil en investissement.</p>
</div></body></html>"""
    return _apply_theme(_html, theme)


def company_report_pdf(r: dict[str, Any], out_path: str | Path, theme: str = "dark") -> Path | None:
    """PDF FIDÈLE à la note HTML complète (toutes sections, graphes, gate de valorisation) via
    weasyprint si présent. Repli reportlab (résumé respectant la gate) sinon ; ou écriture du HTML
    imprimable si aucune lib. `theme` : dark | light. Best-effort : ne lève jamais."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    html = company_report_html(r, theme=theme)
    # 1) weasyprint : rend l'INTÉGRALITÉ du HTML en PDF (identique à l'écran)
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(str(out))
        return out
    except Exception:  # noqa: BLE001 — weasyprint absent/échec → repli reportlab
        pass
    # 2) reportlab : note COMPLÈTE (graphes inclus) respectant la gate
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas
    except Exception:  # noqa: BLE001 — aucune lib PDF → HTML imprimable
        out.with_suffix(".html").write_text(html, encoding="utf-8")
        return None
    _reportlab_pdf(r, str(out), A4, cm, canvas, theme)
    return out


# Palettes PDF (Apple-grade) — sombre & clair
_PDF_DARK = {"bg": "#0b0d10", "card": "#15181d", "fg": "#e8eaed", "muted": "#9aa1ab",
             "border": "#2a2f37", "accent": "#22d3ee", "pos": "#22c55e", "warn": "#f59e0b",
             "neg": "#ef4444", "blue": "#3b82f6"}
_PDF_LIGHT = {"bg": "#ffffff", "card": "#f6f8fa", "fg": "#0b0d10", "muted": "#5b6470",
              "border": "#e3e7ec", "accent": "#0891b2", "pos": "#16a34a", "warn": "#d97706",
              "neg": "#dc2626", "blue": "#2563eb"}


def _reportlab_pdf(r: dict, path: str, A4, cm, canvas, theme: str = "dark") -> None:
    """Note Apple-grade en reportlab : palette couleur, cartes arrondies, badge de score, puces de
    sous-scores, valeurs code-couleur, graphes stylés. Respecte le thème clair/sombre."""
    from reportlab.lib.colors import HexColor
    P = _PDF_LIGHT if theme == "light" else _PDF_DARK
    C = {k: HexColor(v) for k, v in P.items()}

    def tone(score):
        return C["pos"] if score is not None and score >= 65 else C["warn"] if score is not None and score >= 45 else C["neg"]

    idy, sc, ver, dam = r["identity"], r["score"], r["vernimmen"], r["damodaran"]
    dcf = dam.get("dcf", {}); reliable = dcf.get("reliable", True)
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    ML, MR = 1.7 * cm, 1.7 * cm
    CW = w - ML - MR
    st = {"y": h - 1.6 * cm}

    def _bg():
        c.setFillColor(C["bg"]); c.rect(0, 0, w, h, fill=1, stroke=0)

    def _footer():
        c.setFont("Helvetica-Oblique", 7); c.setFillColor(C["muted"])
        c.drawString(ML, 1.1 * cm, "Sources gratuites · cadre Vernimmen & A. Damodaran · aide à la décision, pas un conseil.")
        c.drawRightString(w - MR, 1.1 * cm, str(r.get("as_of", "")))

    _bg()

    def ensure(space):
        if st["y"] - space < 1.8 * cm:
            _footer(); c.showPage(); _bg(); st["y"] = h - 1.6 * cm

    def card(title, rows, *, extra_h=0.0):
        """Carte arrondie : titre accent + lignes (label, valeur, couleur)."""
        row_h = 0.56 * cm
        ch = 1.0 * cm + len(rows) * row_h + extra_h
        ensure(ch + 0.4 * cm)
        top = st["y"]
        c.setFillColor(C["card"]); c.setStrokeColor(C["border"]); c.setLineWidth(0.7)
        c.roundRect(ML, top - ch, CW, ch, 8, fill=1, stroke=1)
        c.setFillColor(C["accent"]); c.setFont("Helvetica-Bold", 9)
        c.drawString(ML + 0.45 * cm, top - 0.6 * cm, title.upper())
        yy = top - 1.15 * cm
        for lab, val, col in rows:
            c.setFont("Helvetica", 9.5); c.setFillColor(C["muted"])
            c.drawString(ML + 0.45 * cm, yy, str(lab))
            c.setFont("Helvetica-Bold", 9.5); c.setFillColor(col or C["fg"])
            c.drawRightString(w - MR - 0.45 * cm, yy, str(val))
            yy -= row_h
        st["y"] = top - ch - 0.35 * cm
        return top, ch

    # ── EN-TÊTE : nom, badge reco/score, puces sous-scores ──
    c.setFillColor(C["muted"]); c.setFont("Helvetica", 8)
    c.drawString(ML, st["y"], f"RAPPORT EFFECTUÉ LE {_fr_date(r.get('as_of'))}")
    st["y"] -= 0.7 * cm
    c.setFillColor(C["fg"]); c.setFont("Helvetica-Bold", 22)
    c.drawString(ML, st["y"], f"{idy['symbol']}")
    _nm = idy.get("name") or ""
    if _nm and _nm != idy["symbol"]:
        st["y"] -= 0.5 * cm
        c.setFillColor(C["muted"]); c.setFont("Helvetica", 11)
        c.drawString(ML, st["y"], _trunc(_nm, 54))
    # badge statut/score à droite — largeur DYNAMIQUE (ne déborde jamais)
    g = sc["global"]
    blocking = (r.get("flags") or {}).get("blocking_alert")
    status = sc.get("verdict_status", sc["recommendation"].upper())
    badge_col = C["neg"] if blocking else tone(g)
    btxt = f"{status} · {g}/100"
    c.setFont("Helvetica-Bold", 10.5)
    bw = c.stringWidth(btxt, "Helvetica-Bold", 10.5) + 0.7 * cm
    bh = 0.95 * cm
    bx, by = w - MR - bw, st["y"] - 0.2 * cm
    c.setFillColor(badge_col); c.roundRect(bx, by, bw, bh, 7, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.drawCentredString(bx + bw / 2, by + 0.32 * cm, btxt)
    st["y"] -= 0.62 * cm
    c.setFillColor(C["muted"]); c.setFont("Helvetica", 9.5)
    c.drawString(ML, st["y"], f"{idy['sector']} · {_money(idy.get('market_cap'))} de capi · cours ${_num(idy.get('price'))}")
    st["y"] -= 0.7 * cm
    # puces sous-scores
    chip_w = 3.7 * cm
    for i, (lab, val) in enumerate([("Fondamental", sc.get("fundamental")),
                                    ("Technique", sc.get("technical")), ("ML", sc.get("ml"))]):
        cx = ML + i * (chip_w + 0.25 * cm)
        c.setFillColor(C["card"]); c.setStrokeColor(C["border"]); c.setLineWidth(0.7)
        c.roundRect(cx, st["y"] - 0.7 * cm, chip_w, 0.95 * cm, 6, fill=1, stroke=1)
        c.setFillColor(C["muted"]); c.setFont("Helvetica", 7.5)
        c.drawString(cx + 0.3 * cm, st["y"] - 0.18 * cm, lab.upper())
        c.setFillColor(tone(val)); c.setFont("Helvetica-Bold", 13)
        c.drawString(cx + 0.3 * cm, st["y"] - 0.58 * cm, f"{val if val is not None else '—'}")
        c.setFillColor(C["muted"]); c.setFont("Helvetica", 7.5)
        c.drawString(cx + 0.3 * cm + c.stringWidth(str(val), "Helvetica-Bold", 13) + 3, st["y"] - 0.58 * cm, "/100")
    st["y"] -= 1.25 * cm

    # ── bannière BLOCKING ALERT ──
    if (r.get("flags") or {}).get("blocking_alert"):
        bhh = 0.95 * cm
        c.setFillColor(C["neg"]); c.roundRect(ML, st["y"] - bhh, CW, bhh, 6, fill=1, stroke=0)
        c.setFillColor(HexColor("#ffffff")); c.setFont("Helvetica-Bold", 9.5)
        c.drawString(ML + 0.4 * cm, st["y"] - 0.6 * cm,
                     "CONTRÔLE REQUIS — réconciliation de données nécessaire · ordre gelé (paper/live)")
        st["y"] -= bhh + 0.35 * cm

    # ── axe directeur (carte accent) ──
    if r.get("memo"):
        lines = _wrap(r["memo"], 105)
        mh = 0.5 * cm + len(lines) * 0.42 * cm
        ensure(mh + 0.3 * cm)
        top = st["y"]
        c.setFillColor(C["card"]); c.roundRect(ML, top - mh, CW, mh, 7, fill=1, stroke=0)
        c.setFillColor(C["accent"]); c.rect(ML, top - mh, 0.09 * cm, mh, fill=1, stroke=0)
        c.setFillColor(C["fg"]); c.setFont("Helvetica-Oblique", 9.5)
        yy = top - 0.4 * cm
        for ln in lines:
            c.drawString(ML + 0.45 * cm, yy, ln); yy -= 0.42 * cm
        st["y"] = top - mh - 0.35 * cm
        if r.get("fx_conversion"):
            c.setFillColor(C["muted"]); c.setFont("Helvetica", 8)
            c.drawString(ML, st["y"], f"converti: {r['fx_conversion']}"); st["y"] -= 0.5 * cm

    # ── Portfolio Snowflake (radar) ──
    snow = r.get("snowflake") or {}
    if snow.get("axes"):
        sh = 5.2 * cm
        ensure(sh + 0.4 * cm)
        top = st["y"]
        c.setFillColor(C["card"]); c.setStrokeColor(C["border"]); c.setLineWidth(0.7)
        c.roundRect(ML, top - sh, CW, sh, 8, fill=1, stroke=1)
        c.setFillColor(C["accent"]); c.setFont("Helvetica-Bold", 9)
        c.drawString(ML + 0.45 * cm, top - 0.6 * cm, "PORTFOLIO SNOWFLAKE")
        _rl_snowflake(c, snow["axes"], ML + 2.6 * cm, top - 3.0 * cm, 1.8 * cm, cm, C)
        # légende à droite
        yy = top - 1.3 * cm
        for k, v in snow["axes"].items():
            c.setFillColor(C["muted"]); c.setFont("Helvetica", 9)
            c.drawString(ML + 6.0 * cm, yy, k)
            c.setFillColor(C["fg"]); c.setFont("Helvetica-Bold", 9)
            c.drawString(ML + 9.5 * cm, yy, f"{v}/100")
            yy -= 0.55 * cm
        c.setFillColor(C["muted"]); c.setFont("Helvetica-Oblique", 8.5)
        c.drawString(ML + 6.0 * cm, top - sh + 0.5 * cm, _trunc(snow.get("summary", ""), 52))
        st["y"] = top - sh - 0.35 * cm

    # ── piliers de notation (barres colorées) — synthèse ──
    pil = sc.get("pillars") or {}
    if pil:
        ph = 1.0 * cm + len(pil) * 0.62 * cm
        ensure(ph + 0.4 * cm)
        top = st["y"]
        c.setFillColor(C["card"]); c.setStrokeColor(C["border"]); c.setLineWidth(0.7)
        c.roundRect(ML, top - ph, CW, ph, 8, fill=1, stroke=1)
        c.setFillColor(C["accent"]); c.setFont("Helvetica-Bold", 9)
        c.drawString(ML + 0.45 * cm, top - 0.6 * cm, "PILIERS DE NOTATION")
        yy = top - 1.15 * cm
        bar_x = ML + 6.0 * cm; bar_w = CW - 6.0 * cm - 1.4 * cm
        for name, p in pil.items():
            val = p.get("score", 0)
            c.setFillColor(C["muted"]); c.setFont("Helvetica", 8.5)
            c.drawString(ML + 0.45 * cm, yy, _trunc(name, 34))
            c.setFillColor(C["border"]); c.roundRect(bar_x, yy - 0.05 * cm, bar_w, 0.22 * cm, 2, fill=1, stroke=0)
            c.setFillColor(tone(val)); c.roundRect(bar_x, yy - 0.05 * cm, bar_w * max(0, min(100, val)) / 100, 0.22 * cm, 2, fill=1, stroke=0)
            c.setFillColor(tone(val)); c.setFont("Helvetica-Bold", 8.5)
            c.drawRightString(w - MR - 0.45 * cm, yy, str(val))
            yy -= 0.62 * cm
        st["y"] = top - ph - 0.35 * cm

    # ── Gouvernance : Audit d'intégrité ──
    audit = r.get("audit") or {}
    rel = audit.get("reliability", "—"); cnt = audit.get("counts", {})
    rel_col = {"fiable": C["pos"], "à vérifier": C["warn"], "non fiable": C["neg"]}.get(rel, C["fg"])
    arows = [("Verdict fiabilité", rel, rel_col),
             ("Critiques · majeures · avert.", f"{cnt.get('critical',0)} · {cnt.get('major',0)} · {cnt.get('warning',0)}", C["fg"])]
    for fd in (audit.get("findings") or [])[:3]:
        arows.append((f"• {fd.get('severity')}", _trunc(fd.get("detail", ""), 60), C["muted"]))
    card("Audit d'intégrité des données", arows)

    # ── Gouvernance : Réconciliation GAAP vs Non-GAAP ──
    rec = r.get("reconciliation")
    if rec and rec.get("rows"):
        rrows = []
        for x in rec["rows"]:
            col = C["pos"] if x["status"] == "réconcilié" else C["warn"] if x["status"] == "écart majeur" else C["neg"]
            rrows.append((f"{x['metric']} (reporté vs GAAP)",
                          f"{_money(x['reported'])} vs {_money(x['gaap'])} · {x['gap']*100:.0f}% · {x['status']}", col))
        card("Réconciliation GAAP vs Non-GAAP", rrows)

    # ── Valorisation (Damodaran, gate-aware) ──
    if not reliable:
        card("Valorisation (Damodaran)", [
            ("Coût des FP · WACC · bêta",
             f"{_pct(dam.get('cost_of_equity'))} · {_pct(dam.get('wacc'))} · {_num(dam.get('beta'))}", C["fg"]),
            ("DCF & multiples", "masqués (devise ≠ cours)", C["warn"]),
        ], extra_h=0.0)
    else:
        scen = dcf.get("scenarios", {}); mos = dcf.get("margin_of_safety"); mu = dam.get("multiples", {})
        _base = scen.get("base"); _dcf_ok = _base is not None and not _isnan(_base)
        drows = []
        if _dcf_ok:
            drows += [
                ("DCF bear / base / bull", f"${_num(scen.get('bear'))} / ${_num(scen.get('base'))} / ${_num(scen.get('bull'))}", C["fg"]),
                ("Marge de sécurité", _pct(mos) if mos is not None else "—", C["pos"] if (mos or 0) > 0 else C["neg"]),
                ("Croissance implicite (cours)", _pct(dam.get("implied_growth_in_price")), C["fg"])]
        else:
            drows.append(("DCF (FCFF)", "non calculable (FCF négatif)", C["muted"]))
        drows += [
            ("P/E · EV/EBITDA · P/B", f"{_num(mu.get('pe'),1)} · {_num(mu.get('ev_ebitda'),1)} · {_num(mu.get('price_to_book'),1)}", C["fg"]),
            ("EV/Sales · rdt FCF · rdt bénéf.", f"{_num(mu.get('ev_sales'),1)} · {_pct(mu.get('fcf_yield'))} · {_pct(mu.get('earnings_yield'))}", C["fg"]),
            ("Coût des FP · bêta", f"{_pct(dam.get('cost_of_equity'))} · {_num(dam.get('beta'))}", C["fg"])]
        card("Valorisation (Damodaran)", drows)

    # ── Rentabilité économique (Vernimmen) ──
    sp = ver.get("value_creation_spread"); eva = ver.get("eva"); m = ver.get("margins", {}); dp = ver.get("dupont", {})
    card("Analyse économique (Vernimmen)", [
        ("ROCE après impôt", _pct(ver.get("roce_after_tax")), C["fg"]),
        ("WACC", _pct(ver.get("wacc")), C["fg"]),
        ("Spread ROCE−WACC", _pct(sp) if sp is not None else "—", C["pos"] if (sp or 0) > 0 else C["neg"]),
        ("EVA (profit économique)", _money(eva), C["pos"] if (eva or 0) > 0 else C["neg"]),
        ("Marges brute / EBIT / nette", f"{_pct(m.get('gross'))} / {_pct(m.get('ebit'))} / {_pct(m.get('net'))}", C["fg"]),
        ("Gearing · Dette nette/EBITDA", f"{_num(ver.get('gearing'))} · {_num(ver.get('net_debt_ebitda'),1)}×", C["fg"]),
        ("DuPont ROE (marge×rotation×levier)",
         f"{_pct(dp.get('net_margin'))}×{_num(dp.get('asset_turnover'))}×{_num(dp.get('equity_multiplier'))} = {_pct(dp.get('roe'))}", C["fg"]),
    ])

    # ── Données financières : graphes + tableaux (exercice & trimestre) ──
    ch_data = r.get("charts") or {}
    closes = ch_data.get("price") or []
    labels = ch_data.get("price_labels") or []
    hist = ch_data.get("financial_history") or []
    if len(closes) >= 20:
        has_bars = len(hist) >= 2
        gh = 7.0 * cm + (5.2 * cm if has_bars else 0)
        ensure(gh + 0.5 * cm)
        top = st["y"]
        c.setFillColor(C["card"]); c.setStrokeColor(C["border"]); c.setLineWidth(0.7)
        c.roundRect(ML, top - gh, CW, gh, 8, fill=1, stroke=1)
        c.setFillColor(C["accent"]); c.setFont("Helvetica-Bold", 9)
        c.drawString(ML + 0.45 * cm, top - 0.6 * cm, "GRAPHIQUES")
        period = (f"{labels[0]} → {labels[-1]}" if len(labels) >= 2 else "")
        gx, gw = ML + 0.9 * cm, CW - 1.4 * cm
        _rl_line(c, closes, labels, gx, top - 4.4 * cm, gw, 2.9 * cm, f"Cours ($) · {period}", cm, C)
        _rl_dd(c, closes, labels, gx, top - 6.7 * cm, gw, 1.4 * cm, "Drawdown (sous l'eau)", cm, C)
        if has_bars:
            half = (gw - 0.8 * cm) / 2
            _rl_bars(c, hist, "revenue", gx, top - gh + 1.0 * cm, half, 2.6 * cm,
                     f"CA ({ch_data.get('history_years', len(hist))} ex.)", cm, C)
            _rl_bars(c, hist, "net_income", gx + half + 0.8 * cm, top - gh + 1.0 * cm, half, 2.6 * cm,
                     "Résultat net", cm, C)
        st["y"] = top - gh - 0.35 * cm

    if len(hist) >= 2:
        trows = []
        for x in hist:
            rev = x.get("revenue"); ni = x.get("net_income"); eps = x.get("eps")
            nm = (ni / rev) if (rev and ni is not None and rev) else None
            trows.append([str(x.get("year", "—")), _money(rev), _money(ni),
                          _num(eps) if eps is not None else "—",
                          (_pct(nm) if nm is not None else "—")])
        _rl_table(c, "Données financières (par exercice)",
                  ["Exercice", "CA", "Résultat net", "BPA", "Marge nette"], trows,
                  ML, CW, st, ensure, cm, C, w, MR)

    qd = r.get("quarterly") or []
    if len(qd) >= 2:
        qrows = []
        for x in qd:
            nm = x.get("net_margin")
            qrows.append([str(x.get("period", "—")), _money(x.get("revenue")), _money(x.get("net_income")),
                          _num(x.get("eps")) if x.get("eps") is not None else "—",
                          _pct(nm) if nm is not None else "—"])
        _rl_table(c, "Données financières (par trimestre)",
                  ["Trimestre", "CA", "Résultat net", "BPA", "Marge nette"], qrows,
                  ML, CW, st, ensure, cm, C, w, MR)

    # ── positionnement secteur ──
    scmp = r.get("sector_comparison") or {}
    if scmp.get("available"):
        rows = []
        for x in scmp.get("rows", []):
            isr = x["metric"] in ("net_margin", "roe", "roic", "gross_margin", "revenue_growth")
            cv = _pct(x["company"]) if isr else _num(x["company"])
            mv = _pct(x["sector_median"]) if isr else _num(x["sector_median"])
            col = C["pos"] if x["verdict"] == "favorable" else C["neg"]
            rows.append((f"{x['label']} (méd. {mv})", f"{cv} · {int(x['percentile']*100)}e · {x['verdict']}", col))
        card(f"Positionnement sectoriel ({scmp.get('favorable')}/{scmp.get('total')} favorables · {scmp.get('n_peers')} pairs)", rows)

    # ── qualité ──
    ql = r["quality"]; z = ql.get("altman_z", {}); inv = ql.get("investor_scores", {})
    card("Qualité & solidité", [
        ("Piotroski F-score", f"{ql.get('piotroski_f_score')}/9 ({ql.get('piotroski_label')})", C["fg"]),
        ("Altman Z", f"{z.get('z')} ({z.get('zone')})" if z.get("z") is not None else "N/A", C["fg"]),
        ("Graham / Fisher / Thiel", f"{inv.get('graham')} / {inv.get('fisher')} / {inv.get('thiel')}", C["fg"]),
    ])

    # ── risk management de l'actif ──
    rk = r.get("risk") or {}
    if rk.get("available"):
        card("Risk management de l'actif", [
            ("Volatilité annualisée", _pct(rk.get("vol_annual")), C["fg"]),
            ("Max drawdown · VaR 95 %", f"{_pct(rk.get('max_drawdown'))} · {_pct(rk.get('var_95'))}", C["neg"]),
            ("CVaR 95 % (1j)", _pct(rk.get("cvar_95")), C["neg"]),
            ("Sharpe / Sortino", f"{_num(rk.get('sharpe'))} / {_num(rk.get('sortino'))}", C["fg"]),
            ("Bêta marché", _num(rk.get("beta")) if rk.get("beta") is not None else "—", C["fg"]),
            ("Stop suggéré (~2σ hebdo)", _pct(rk.get("suggested_stop")), C["warn"]),
        ])

    # ── technique ──
    t = r.get("technical")
    if t:
        trend = str(t.get("trend") or "—")
        tcol = C["pos"] if trend == "haussière" else C["neg"] if trend == "baissière" else C["fg"]
        card("Analyse technique", [
            ("Tendance · RSI · MACD", f"{trend} · {_num(t.get('rsi'),0)} · {t.get('macd_signal','—')}", tcol),
            ("vs MM50 / MM200", f"{_pct(t.get('vs_sma50'))} / {_pct(t.get('vs_sma200'))}", C["fg"]),
            ("Plage 52 sem.", f"${_num(t.get('low_52w'),0)} – ${_num(t.get('high_52w'),0)}", C["muted"]),
        ])

    # ── macro + résultats ──
    rows = []
    mc = r.get("macro")
    if mc:
        rows.append(("Régime · VIX", f"{mc.get('regime') or 'neutre'} · {_num(mc.get('vix'),1)}", C["fg"]))
        rows.append(("Exposition · Taux 10A US",
                     f"{_pct(mc.get('exposure')) if mc.get('exposure') is not None else '60%'} · "
                     f"{_pct(mc.get('rate_10y')) if mc.get('rate_10y') is not None else '4.3%'}", C["fg"]))
    e = r.get("earnings")
    if e:
        rows += [("Prochain résultat", e.get("next_date") or "—", C["accent"]),
                 ("BPA estimé / annoncé", f"{_num(e.get('eps_estimate'))} / {_num(e.get('eps_actual')) if e.get('eps_actual') is not None else '—'}", C["fg"]),
                 ("Revenu estimé / annoncé", f"{_money(e.get('revenue_estimate'))} / {_money(e.get('revenue_actual')) if e.get('revenue_actual') is not None else '—'}", C["fg"])]
    if rows:
        card("Macro & résultats", rows)

    # ── actionnariat (barres horizontales) ──
    hd = r.get("holders") or {}
    inst = hd.get("institutional") or []; insi = hd.get("insiders") or []
    if inst or insi:
        _rl_holders(c, inst, insi, ML, CW, st, ensure, cm, C, w, MR)

    # ── verdict ──
    v = r.get("verdict", {})
    if v.get("strengths") or v.get("watch"):
        rows = [("✓ " + s, "", C["pos"]) for s in v.get("strengths", [])[:4]]
        rows += [("▸ " + s, "", C["warn"]) for s in v.get("watch", [])[:4]]
        # wrap long lines into the label column (value empty)
        wrapped = []
        for lab, _, col in rows:
            for j, ln in enumerate(_wrap(lab, 95)):
                wrapped.append((ln if j == 0 else "   " + ln, "", col))
        card("Synthèse Advisory Board — Moat & Tail Risk", wrapped)

    _footer(); c.showPage(); c.save()


def _rl_line(c, vals, labels, x, y, w, h, title, cm, C=None) -> None:
    """Courbe (cours) reportlab : axe Y ($), axe X DATÉ, aire + ligne accent. C = palette couleur."""
    from reportlab.lib.colors import HexColor
    acc = C["accent"] if C else HexColor("#22d3ee")
    mut = C["muted"] if C else HexColor("#9aa1ab")
    bdr = C["border"] if C else HexColor("#2a2f37")
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    x0 = x + 1.0 * cm
    c.setFillColor(mut); c.setFont("Helvetica", 8); c.drawString(x, y + h + 4, title)
    c.setStrokeColor(bdr); c.setLineWidth(0.5)
    for k in range(4):
        yy = y + h * k / 3
        c.line(x0, yy, x + w, yy)
        c.setFillColor(mut); c.setFont("Helvetica", 6.5)
        c.drawRightString(x + 0.9 * cm, yy - 2, f"${_num(lo + rng * k / 3, 0)}")
    n = len(vals)
    pts = [(x0 + i * (w - 1.0 * cm) / (n - 1), y + (v - lo) / rng * h) for i, v in enumerate(vals)]
    c.setStrokeColor(acc); c.setLineWidth(1.2)
    for a, b in zip(pts[:-1], pts[1:]):
        c.line(a[0], a[1], b[0], b[1])
    if labels and len(labels) >= 2:
        c.setFillColor(mut); c.setFont("Helvetica", 6.5)
        for frac, draw in ((0.0, c.drawString), (0.5, c.drawCentredString), (1.0, c.drawRightString)):
            idx = min(len(labels) - 1, int(frac * (len(labels) - 1)))
            draw(x0 + (w - 1.0 * cm) * frac, y - 9, str(labels[idx]))


def _rl_bars(c, hist, key, x, y, w, h, title, cm, C=None) -> None:
    """Barres annuelles (CA/résultat) reportlab — gère les valeurs NÉGATIVES (ligne de zéro, barres
    au-dessus/en-dessous, libellés positionnés sans déborder). `y` = base de la zone du graphe."""
    from reportlab.lib.colors import HexColor
    acc = C["accent"] if C else HexColor("#22d3ee")
    neg = C["neg"] if C else HexColor("#ef4444")
    mut = C["muted"] if C else HexColor("#9aa1ab")
    fg = C["fg"] if C else HexColor("#e8eaed")
    vals = [float(d.get(key) or 0) for d in hist]
    hi = max(vals + [0.0]); lo = min(vals + [0.0])
    span = (hi - lo) or 1.0
    pad = 0.32 * cm                                        # marge haut/bas pour les libellés de valeur
    bot, h2 = y + pad, h - 2 * pad                         # zone réservée aux barres
    zero = bot + (0 - lo) / span * h2                      # ordonnée de la ligne du zéro
    c.setFillColor(mut); c.setFont("Helvetica", 8); c.drawString(x, y + h + 4, title)
    c.setStrokeColor(C["border"] if C else HexColor("#2a2f37")); c.setLineWidth(0.5)
    c.line(x + 1.0 * cm, zero, x + w, zero)               # ligne du zéro
    n = len(vals); gap = (w - 1.0 * cm) / n; bw = gap * 0.56
    for i, (d, v) in enumerate(zip(hist, vals)):
        vy = bot + (v - lo) / span * h2
        bx = x + 1.0 * cm + i * gap + (gap - bw) / 2
        top = max(vy, zero); bh = abs(vy - zero)
        c.setFillColor(acc if v >= 0 else neg)
        c.roundRect(bx, min(vy, zero), bw, max(1, bh), 2, fill=1, stroke=0)
        c.setFillColor(fg); c.setFont("Helvetica", 6.5)
        ly = (top + 3) if v >= 0 else (min(vy, zero) - 7)  # au-dessus si positif, en-dessous si négatif
        c.drawCentredString(bx + bw / 2, ly, _money_axis(v))
        c.setFillColor(mut); c.drawCentredString(bx + bw / 2, y - 9, str(d.get("year", "")))


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = str(text).split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > width:
            lines.append(cur); cur = wd
        else:
            cur = (cur + " " + wd).strip()
    if cur:
        lines.append(cur)
    return lines[:8]


def company_report_markdown(r: dict[str, Any]) -> str:
    """Rendu Markdown Obsidian de la note — concis, fort impact, front matter Dataview + wikilinks.
    Quality over quantity : uniquement les chiffres décisifs. Réutilisable dans le coffre."""
    idy, sc, ver, dam, ql = r["identity"], r["score"], r["vernimmen"], r["damodaran"], r["quality"]
    dcf = dam.get("dcf", {}); scen = dcf.get("scenarios", {})
    fm = ["---", "type: company_report", f"symbol: {idy['symbol']}", f"sector: {idy.get('sector','')}",
          f"score: {sc.get('global')}", f"recommendation: {sc.get('recommendation')}",
          f"roce: {ver.get('roce_after_tax')}", f"wacc: {ver.get('wacc')}",
          f"margin_of_safety: {dcf.get('margin_of_safety')}", "tags: [quant, company]",
          f"updated: {r.get('as_of')}", "---"]
    rel = {"fiable": "✅", "à vérifier": "⚠️", "non fiable": "⛔"}.get(r.get("audit", {}).get("reliability"), "")
    spread = ver.get("value_creation_spread")
    body = [
        "", f"# 🏢 {idy['name']} ({idy['symbol']})", "",
        f"> [!abstract] **{sc.get('recommendation')} · {sc.get('global')}/100** "
        f"(fond {sc.get('fundamental')} · tech {sc.get('technical')} · ml {sc.get('ml')}) {rel}",
        f"> {r.get('memo','')}", "",
        "## Décideurs", "", "| Indicateur | Valeur |", "|---|--:|",
        f"| ROCE − WACC | {_pct(spread) if spread is not None else '—'} |",
        f"| EVA | {_money(ver.get('eva'))} |",
        f"| Marge nette | {_pct(ver.get('margins',{}).get('net'))} |",
        f"| DCF base / sécurité | ${_num(scen.get('base'))} / {_pct(dcf.get('margin_of_safety')) if dcf.get('margin_of_safety') is not None else '—'} |",
        f"| Piotroski / Altman Z | {ql.get('piotroski_f_score')}/9 · {ql.get('altman_z',{}).get('z')} |",
    ]
    scmp = r.get("sector_comparison") or {}
    if scmp.get("available"):
        body.append(f"| Vs secteur | {scmp.get('favorable')}/{scmp.get('total')} favorables |")
    v = r.get("verdict", {})
    if v.get("strengths"):
        body += ["", "## Forces", "", *[f"- ✅ {s}" for s in v["strengths"][:4]]]
    if v.get("watch"):
        body += ["", "## Vigilance", "", *[f"- ⚠️ {s}" for s in v["watch"][:4]]]
    body += ["", f"<small>Sources gratuites · Vernimmen & Damodaran · maj {r.get('as_of')}.</small>"]
    return "\n".join(fm + body)


def _trunc(s: str, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def _rl_dd(c, closes, labels, x, y, w, h, title, cm, C=None) -> None:
    """Courbe de drawdown (sous l'eau) reportlab : axe Y en %, dates en X."""
    from reportlab.lib.colors import HexColor
    neg = C["neg"] if C else HexColor("#ef4444")
    mut = C["muted"] if C else HexColor("#9aa1ab")
    bdr = C["border"] if C else HexColor("#2a2f37")
    peak, dd = closes[0], []
    for v in closes:
        peak = max(peak, v); dd.append(v / peak - 1.0 if peak else 0.0)
    lo = min(dd); rng = (0.0 - lo) or 1.0
    x0 = x + 1.0 * cm
    c.setFillColor(mut); c.setFont("Helvetica", 8); c.drawString(x, y + h + 4, title)
    c.setStrokeColor(bdr); c.setLineWidth(0.5)
    for k in range(3):
        yy = y + h * k / 2
        c.line(x0, yy, x + w, yy)
        c.setFillColor(mut); c.setFont("Helvetica", 6.5)
        c.drawRightString(x + 0.9 * cm, yy - 2, f"{(0.0 - rng*(1-k/2))*100:.0f}%")
    n = len(dd)
    pts = [(x0 + i * (w - 1.0 * cm) / (n - 1), y + (v - lo) / rng * h) for i, v in enumerate(dd)]
    c.setStrokeColor(neg); c.setLineWidth(1.1)
    for a, b in zip(pts[:-1], pts[1:]):
        c.line(a[0], a[1], b[0], b[1])


def _rl_table(c, title, headers, rows, ML, CW, st, ensure, cm, C, w, MR) -> None:
    """Tableau (Données financières) reportlab dans une carte arrondie, colonnes alignées à droite."""
    row_h = 0.5 * cm
    th = 1.3 * cm + (len(rows) + 1) * row_h
    ensure(th + 0.4 * cm)
    top = st["y"]
    c.setFillColor(C["card"]); c.setStrokeColor(C["border"]); c.setLineWidth(0.7)
    c.roundRect(ML, top - th, CW, th, 8, fill=1, stroke=1)
    c.setFillColor(C["accent"]); c.setFont("Helvetica-Bold", 9)
    c.drawString(ML + 0.45 * cm, top - 0.6 * cm, title.upper())
    ncol = len(headers)
    x0 = ML + 0.45 * cm
    colw = (CW - 0.9 * cm) / ncol
    yy = top - 1.25 * cm
    c.setFont("Helvetica", 7.5); c.setFillColor(C["muted"])
    for j, hd in enumerate(headers):
        (c.drawString if j == 0 else c.drawRightString)(
            x0 + (j * colw if j == 0 else (j + 1) * colw - 0.2 * cm), yy, hd)
    yy -= row_h
    for row in rows:
        c.setStrokeColor(C["border"]); c.setLineWidth(0.3); c.line(x0, yy + 0.32 * cm, ML + CW - 0.45 * cm, yy + 0.32 * cm)
        c.setFont("Helvetica", 8.5)
        for j, cell in enumerate(row):
            c.setFillColor(C["fg"] if j == 0 else C["fg"])
            (c.drawString if j == 0 else c.drawRightString)(
                x0 + (j * colw if j == 0 else (j + 1) * colw - 0.2 * cm), yy, str(cell))
        yy -= row_h
    st["y"] = top - th - 0.35 * cm


def _rl_holders(c, inst, insi, ML, CW, st, ensure, cm, C, w, MR) -> None:
    """Carte « Actionnariat » reportlab : barres horizontales (institutionnels % · insiders titres)."""
    def _series(rows, key):
        return [(str(x.get("name") or "—"), x.get(key)) for x in rows if x.get(key) is not None][:5]
    si = _series(inst, "pct")
    _ik = "pct" if any(x.get("pct") is not None for x in insi) else "shares"
    sn = _series(insi, _ik); _ins_pct = (_ik == "pct")
    nlines = max(len(si), len(sn))
    if nlines == 0:
        return
    hh = 1.45 * cm + nlines * 0.62 * cm
    ensure(hh + 0.4 * cm)
    top = st["y"]
    c.setFillColor(C["card"]); c.setStrokeColor(C["border"]); c.setLineWidth(0.7)
    c.roundRect(ML, top - hh, CW, hh, 8, fill=1, stroke=1)
    c.setFillColor(C["accent"]); c.setFont("Helvetica-Bold", 9)
    c.drawString(ML + 0.45 * cm, top - 0.6 * cm, "ACTIONNARIAT — RÉPARTITION")
    colw = (CW - 1.2 * cm) / 2

    def _draw(series, x0, title, is_pct):
        c.setFillColor(C["muted"]); c.setFont("Helvetica", 7.5)
        c.drawString(x0, top - 1.15 * cm, title)
        mx = max((v for _, v in series), default=1.0) or 1.0
        yy = top - 1.6 * cm
        for name, v in series:
            c.setFillColor(C["fg"]); c.setFont("Helvetica", 7.5)
            c.drawString(x0, yy + 0.12 * cm, _trunc(name, 22))
            lab = f"{v*100:.1f}%" if is_pct else _money_axis(v)
            c.setFillColor(C["muted"]); c.drawRightString(x0 + colw - 0.1 * cm, yy + 0.12 * cm, lab)
            c.setFillColor(C["border"]); c.roundRect(x0, yy - 0.05 * cm, colw - 0.1 * cm, 0.16 * cm, 2, fill=1, stroke=0)
            c.setFillColor(C["accent"]); c.roundRect(x0, yy - 0.05 * cm, (colw - 0.1 * cm) * max(0.04, v / mx), 0.16 * cm, 2, fill=1, stroke=0)
            yy -= 0.62 * cm

    if si:
        _draw(si, ML + 0.45 * cm, "Top institutionnels (% capital)", True)
    if sn:
        _draw(sn, ML + 0.65 * cm + colw, "Top insiders (% capital)" if _ins_pct else "Top insiders (titres)", _ins_pct)
    st["y"] = top - hh - 0.35 * cm


def _rl_snowflake(c, axes, cx, cy, R, cm, C) -> None:
    """Radar « Portfolio Snowflake » reportlab : anneaux + polygone doré (5 axes)."""
    import math
    from reportlab.lib.colors import HexColor
    gold = HexColor("#e0b015")
    labels = ["VALUE", "FUTURE", "PAST", "HEALTH", "DIVIDEND"]
    n = len(labels)
    def _pt(i, rad):
        a = -math.pi / 2 + i * 2 * math.pi / n
        return cx + rad * math.cos(a), cy + rad * math.sin(a)
    c.setStrokeColor(C["border"]); c.setLineWidth(0.5)
    for k in (0.33, 0.66, 1.0):                            # anneaux
        pts = [_pt(i, R * k) for i in range(n)]
        p = c.beginPath(); p.moveTo(*pts[0])
        for q in pts[1:]:
            p.lineTo(*q)
        p.close(); c.drawPath(p, stroke=1, fill=0)
    for i in range(n):                                     # rayons + labels
        ex, ey = _pt(i, R)
        c.line(cx, cy, ex, ey)
        lx, ly = _pt(i, R + 0.35 * cm)
        c.setFillColor(C["muted"]); c.setFont("Helvetica", 6)
        c.drawCentredString(lx, ly - 2, labels[i])
    poly = c.beginPath()                                   # polygone des scores
    pts = [_pt(i, R * max(0.05, axes.get(labels[i], 0) / 100)) for i in range(n)]
    poly.moveTo(*pts[0])
    for q in pts[1:]:
        poly.lineTo(*q)
    poly.close()
    c.setFillColor(gold); c.setStrokeColor(gold); c.setLineWidth(1.2)
    c.setFillAlpha(0.75); c.drawPath(poly, stroke=1, fill=1); c.setFillAlpha(1)
