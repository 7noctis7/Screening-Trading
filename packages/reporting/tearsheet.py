"""Tear sheet de performance — HTML (toujours) + PDF (reportlab).

Résumé visuel d'un backtest/portefeuille : métriques clés + courbe d'equity (vs benchmark).
HTML autonome rendu partout ; PDF via reportlab pour archivage/partage.
"""

from __future__ import annotations

from pathlib import Path

_C = {"bg": "#0a0b0d", "surface": "#141619", "border": "#262a31", "fg": "#e6e8eb",
      "muted": "#9aa1ab", "accent": "#3b82f6", "pos": "#22c55e", "neg": "#ef4444"}


def _polyline(values, w, h, pad=6):
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1.0
    n = len(values)
    return " ".join(f"{pad + i*(w-2*pad)/(n-1):.1f},{h-pad-(v-lo)/rng*(h-2*pad):.1f}"
                    for i, v in enumerate(values))


def build_tearsheet_html(title: str, metrics: dict, equity: list[float],
                         benchmarks: dict[str, list[float]] | None = None) -> str:
    rows = "".join(
        f'<tr style="border-top:1px solid {_C["border"]}">'
        f'<td style="padding:6px 0;color:{_C["muted"]}">{k}</td>'
        f'<td style="text-align:right;font-variant-numeric:tabular-nums">{v}</td></tr>'
        for k, v in metrics.items())
    port = _polyline(equity, 720, 200)
    bench_lines = ""
    for name, curve in (benchmarks or {}).items():
        bench_lines += (f'<polyline points="{_polyline(curve, 720, 200)}" fill="none" '
                        f'stroke="{_C["muted"]}" stroke-width="1.2" opacity="0.5"/>')
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body style="margin:0;background:{_C['bg']};color:{_C['fg']};
font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Inter,system-ui,sans-serif">
<div style="max-width:780px;margin:0 auto;padding:24px;display:flex;flex-direction:column;gap:14px">
<h1 style="font-size:20px;font-weight:600;margin:0">{title}</h1>
<div style="background:{_C['surface']};border:1px solid {_C['border']};border-radius:16px;padding:18px">
<svg viewBox="0 0 720 200" width="100%" height="200">{bench_lines}
<polyline points="{port}" fill="none" stroke="{_C['accent']}" stroke-width="2"/></svg></div>
<div style="background:{_C['surface']};border:1px solid {_C['border']};border-radius:16px;padding:18px">
<table style="width:100%;font-size:14px">{rows}</table></div>
</div></body></html>"""


def to_pdf(title: str, metrics: dict, equity: list[float], out_path: str | Path) -> Path:
    """Tear sheet PDF via reportlab (courbe d'equity + table de métriques)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out), pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, h - 2 * cm, title)
    # courbe d'equity
    x0, y0, cw, ch = 2 * cm, h - 11 * cm, w - 4 * cm, 7 * cm
    if len(equity) >= 2:
        lo, hi = min(equity), max(equity)
        rng = (hi - lo) or 1.0
        pts = [(x0 + i * cw / (len(equity) - 1), y0 + (v - lo) / rng * ch)
               for i, v in enumerate(equity)]
        c.setStrokeColorRGB(0.23, 0.51, 0.96)
        c.setLineWidth(1.4)
        for a, b in zip(pts[:-1], pts[1:]):
            c.line(a[0], a[1], b[0], b[1])
    # métriques
    c.setFont("Helvetica", 11)
    y = y0 - 1.5 * cm
    for k, v in metrics.items():
        c.drawString(2 * cm, y, str(k))
        c.drawRightString(w - 2 * cm, y, str(v))
        y -= 0.7 * cm
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(2 * cm, 1.5 * cm,
                 "Données synthétiques — pas un conseil en investissement.")
    c.showPage(); c.save()
    return out
