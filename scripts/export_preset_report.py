"""Rapport HTML autonome du backtest preset + volatilité gérée (courbes + drawdowns + tables).

  export QUANT_PRICE_DB=/chemin/YAHOO.db   # sinon synthétique
  python scripts/export_preset_report.py   # → out/preset_report.html (ouvrable au navigateur)

Aucune dépendance : graphiques en SVG inline, thème sombre type terminal. Tout point-in-time.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

W, H, PADL, PADR, PADT, PADB = 900, 300, 52, 16, 14, 26
COLORS = {"preset": "#22d3ee", "swing": "#f59e0b", "benchmark": "#9aa1ab",
          "S&P 500": "#f59e0b", "Nasdaq 100": "#a855f7", "Portefeuille": "#22d3ee"}


def _path(vals: list[float], lo: float, hi: float, n: int) -> str:
    rng = (hi - lo) or 1.0
    pts = []
    for i, v in enumerate(vals):
        x = PADL + (W - PADL - PADR) * (i / max(1, n - 1))
        y = PADT + (H - PADT - PADB) * (1 - (v - lo) / rng)
        pts.append(f"{x:.1f},{y:.1f}")
    return "M" + " L".join(pts)


def _line_chart(series: dict[str, list[float]], title: str, fmt=lambda v: f"{v:.2f}") -> str:
    series = {k: v for k, v in series.items() if v}
    if not series:
        return ""
    allv = [x for v in series.values() for x in v]
    lo, hi = min(allv), max(allv)
    n = max(len(v) for v in series.values())
    grid = "".join(
        f'<line x1="{PADL}" y1="{PADT + (H-PADT-PADB)*f:.1f}" x2="{W-PADR}" '
        f'y2="{PADT + (H-PADT-PADB)*f:.1f}" stroke="#1b2630"/>'
        f'<text x="6" y="{PADT + (H-PADT-PADB)*f + 3:.1f}" fill="#5d6f78" font-size="10">'
        f'{fmt(hi - (hi-lo)*f)}</text>' for f in (0, 0.25, 0.5, 0.75, 1.0))
    paths = "".join(
        f'<path d="{_path(v, lo, hi, n)}" fill="none" stroke="{COLORS.get(k, "#5eead4")}" '
        f'stroke-width="1.8"/>' for k, v in series.items())
    legend = " ".join(
        f'<span style="color:{COLORS.get(k, "#5eead4")}">━ {k}</span>' for k in series)
    return (f'<div class="card"><div class="h">{title}</div>'
            f'<svg viewBox="0 0 {W} {H}" width="100%" preserveAspectRatio="xMidYMid meet">'
            f'{grid}{paths}</svg><div class="leg">{legend}</div></div>')


def _underwater(equity: list[float], title: str) -> str:
    if not equity:
        return ""
    peak, dd = equity[0], []
    for v in equity:
        peak = max(peak, v)
        dd.append(v / peak - 1)
    lo, hi = min(dd), 0.0
    rng = (hi - lo) or 1.0
    n = len(dd)
    pts = [f"{PADL},{PADT + (H-PADT-PADB)*(1-(0-lo)/rng):.1f}"]
    for i, v in enumerate(dd):
        x = PADL + (W - PADL - PADR) * (i / max(1, n - 1))
        y = PADT + (H - PADT - PADB) * (1 - (v - lo) / rng)
        pts.append(f"{x:.1f},{y:.1f}")
    pts.append(f"{W-PADR},{PADT + (H-PADT-PADB)*(1-(0-lo)/rng):.1f}")
    area = "M" + " L".join(pts) + " Z"
    label = f'<text x="6" y="{PADT+3}" fill="#5d6f78" font-size="10">0%</text>' \
            f'<text x="6" y="{H-PADB:.0f}" fill="#f43f5e" font-size="10">{lo*100:.0f}%</text>'
    return (f'<div class="card"><div class="h">{title}</div>'
            f'<svg viewBox="0 0 {W} {H}" width="100%" preserveAspectRatio="xMidYMid meet">'
            f'<path d="{area}" fill="rgba(244,63,94,.25)" stroke="#f43f5e" stroke-width="1.2"/>'
            f'{label}</svg></div>')


def _table(title: str, headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="card"><div class="h">{title}</div><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def main() -> None:
    from apps.api.snapshot import build_snapshot
    print("Construction du snapshot…")
    s = build_snapshot()
    meta, dash = s["meta"], s["dashboard"]
    a = s["portfolio"]["analysis"]
    pb = (a.get("recommended_allocation") or {}).get("preset_backtest") or {}
    vm = (a.get("risk") or {}).get("vol_managed") or {}

    blocks = []

    # 1) Equity swing vs benchmarks (quotidien, dates réelles)
    eq = [p["v"] for p in dash.get("equity", [])]
    ben47 = {"Portefeuille": eq}
    for name, pts in (dash.get("benchmarks") or {}).items():
        ben47[name] = [p["v"] for p in pts]
    blocks.append(_line_chart(ben47, "Equity — portefeuille (swing) vs benchmarks ($)",
                              fmt=lambda v: f"{v/1000:.0f}k" if abs(v) >= 1000 else f"{v:.0f}"))
    blocks.append(_underwater(eq, "Drawdown du portefeuille (underwater)"))

    # 2) Preset vs swing vs équipondéré (base 1.0)
    if pb.get("available") and pb.get("curves"):
        blocks.append(_line_chart(pb["curves"], "Preset vs Swing vs Équipondéré (base 1.0, walk-forward)"))
        rows = []
        for lab, key in (("Preset (best practice)", "preset"), ("Swing (actuel)", "swing"),
                         ("Équipondéré (même univers)", "benchmark")):
            st = pb.get(key)
            if st:
                rows.append([lab, f"{st['annualized']*100:.1f}%", f"{st['sharpe']}",
                             f"{st['max_drawdown']*100:.1f}%", f"{st['total_return']*100:.1f}%"])
        blocks.append(_table(f"Preset — stats (top {pb['top_k']}, pas {pb['step_days']} j, "
                             f"turnover {pb['turnover_annual']}×/an)",
                             ["Stratégie", "CAGR", "Sharpe", "Max DD", "Rdt tot."], rows))

    # 3) Volatilité gérée (Moreira-Muir)
    if vm.get("available"):
        rows = [[lab, f"{vm[k]['cagr']*100:.1f}%", f"{vm[k]['sharpe']}",
                 f"{vm[k]['max_drawdown']*100:.1f}%", f"{vm[k]['vol']*100:.1f}%"]
                for lab, k in (("Brute", "raw"), ("Volatilité gérée", "managed"))]
        blocks.append(_table(f"Volatilité gérée (Moreira-Muir, vol-cible {vm['target_vol']*100:.0f}%, "
                             f"expo moy. {vm['avg_exposure']*100:.0f}%)",
                             ["Série", "CAGR", "Sharpe", "Max DD", "Vol"], rows))

    html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rapport preset — Quant Terminal</title><style>
:root{{color-scheme:dark}}
body{{margin:0;background:#0a1118;color:#eaf2f4;font-family:-apple-system,BlinkMacSystemFont,Inter,system-ui,sans-serif;padding:24px;max-width:960px;margin:0 auto}}
h1{{font-size:20px;letter-spacing:-.02em}}.sub{{color:#8fa3ad;font-size:13px;margin-bottom:18px}}
.card{{background:linear-gradient(180deg,#121c26,#0e1721);border:1px solid #22303c;border-radius:14px;padding:16px;margin-bottom:16px}}
.h{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#8fa3ad;margin-bottom:10px}}
.leg{{font-size:12px;color:#8fa3ad;margin-top:6px;display:flex;gap:16px;flex-wrap:wrap}}
table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:13px}}
th{{text-align:right;color:#5d6f78;font-weight:600;font-size:10px;text-transform:uppercase;padding:6px 8px;border-bottom:1px solid #22303c}}
th:first-child,td:first-child{{text-align:left}}td{{text-align:right;padding:7px 8px;border-top:1px solid #1b2630;font-family:"SF Mono",monospace}}
.note{{color:#5d6f78;font-size:12px;margin-top:8px}}
</style></head><body>
<h1>📊 Rapport backtest — Preset « best practice » + Volatilité gérée</h1>
<div class="sub">Mode des données : <b>{meta['mode']}</b> · univers {meta['universe_size']} · généré le {meta['generated_at'][:16].replace('T',' ')} · point-in-time (anti-fuite)</div>
{''.join(blocks)}
<div class="note">Lecture honnête : viser le meilleur <b>Sharpe</b> et le plus faible <b>drawdown</b>, pas le CAGR brut. Sans edge directionnel prouvé (DSR≈0), la gestion du risque (risk-parity, DD-target, vol-targeting, no-trade band) est le levier fiable. Le bénéfice de la volatilité gérée vient du clustering de vol des marchés réels.</div>
</body></html>"""

    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    dest = out / "preset_report.html"
    dest.write_text(html, encoding="utf-8")
    print(f"✅ Rapport écrit : {dest}")
    print("   Ouvre-le au navigateur (double-clic) ou : open out/preset_report.html")


if __name__ == "__main__":
    main()
