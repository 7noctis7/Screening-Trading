"""Export d'un **tear sheet** de performance — HTML (toujours) + PDF (si reportlab).

  python scripts/export_tearsheet.py                 # → out/tearsheet.html (+ .pdf si dispo)
  python scripts/export_tearsheet.py --out rapports  # dossier de sortie personnalisé

Best practices : aucune dépendance obligatoire (HTML autonome), PDF optionnel et dégradé
proprement, mention « pas un conseil » conservée. Données = snapshot courant (réel ou synthétique).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Exporte un tear sheet (HTML + PDF optionnel)")
    ap.add_argument("--out", default="out", help="dossier de sortie (défaut: out/)")
    a = ap.parse_args()

    from apps.api.snapshot import build_snapshot
    from packages.reporting import build_tearsheet_html, to_pdf

    snap = build_snapshot()
    m = snap["portfolio"]["metrics"]
    k = snap["dashboard"]["portfolio"]
    equity = [pt["v"] if isinstance(pt, dict) else pt for pt in snap["dashboard"]["equity"]]
    title = f"Quant Terminal — Tear sheet ({snap['meta'].get('mode')})"
    metrics = {
        "Valeur portefeuille": f"{k['value']:,.0f} $",
        "P&L": f"{k['pnl_pct'] * 100:+.1f} %",
        "Rendement total": f"{m['total_return'] * 100:.1f} %",
        "Sharpe": f"{m['sharpe']:.2f}", "Sortino": f"{m['sortino']:.2f}",
        "Calmar": f"{m['calmar']:.2f}", "Max drawdown": f"{m['max_drawdown'] * 100:.1f} %",
        "Win rate": f"{m['win_rate'] * 100:.0f} %", "Profit factor": f"{m['profit_factor']:.2f}",
        "Positions": str(k["n_positions"]),
    }

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "tearsheet.html"
    html_path.write_text(build_tearsheet_html(title, metrics, equity), encoding="utf-8")
    print(f"écrit : {html_path}")

    try:
        pdf_path = to_pdf(title, metrics, equity, out_dir / "tearsheet.pdf")
        print(f"écrit : {pdf_path}")
    except ModuleNotFoundError:
        print("PDF ignoré (reportlab non installé) — `pip install reportlab` pour l'activer.")


if __name__ == "__main__":
    main()
