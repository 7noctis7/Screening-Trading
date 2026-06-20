#!/usr/bin/env python3
"""Pré-génération nocturne des notes d'analyse par société → out/notes/AAAA-MM-JJ/.

Génère les notes (HTML + PDF si reportlab) du TOP-CONVICTION et des positions détenues, pour une
consultation instantanée et un historique daté. À lancer par le cron quotidien (après le build).
Best-effort : ne crashe jamais ; saute proprement un titre en échec.

    python scripts/generate_reports.py                 # top 30 conviction + positions
    python scripts/generate_reports.py --top 50 --tickers AAPL,MSFT
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _targets(top: int) -> list[str]:
    """Univers cible : top-conviction + positions détenues (déduit du snapshot)."""
    syms: list[str] = []
    try:
        from apps.api.snapshot import build_snapshot
        snap = build_snapshot()
        conv = (snap.get("conviction", {}) or {}).get("rows", []) or []
        syms += [r.get("symbol") for r in conv[:top] if r.get("symbol")]
        held = (snap.get("portfolio", {}) or {}).get("open_trades", []) or []
        syms += [r.get("symbol") for r in held if r.get("symbol")]
    except Exception as e:  # noqa: BLE001
        print(f"snapshot indisponible ({e}) — rien à générer.")
    # dédup en conservant l'ordre
    return list(dict.fromkeys(s for s in syms if s))


def main() -> int:
    ap = argparse.ArgumentParser(description="Pré-génère les notes d'analyse par société")
    ap.add_argument("--top", type=int, default=30, help="nombre de titres conviction")
    ap.add_argument("--tickers", help="liste explicite (CSV) au lieu du top-conviction")
    ap.add_argument("--out", default=None, help="dossier de sortie (défaut out/notes/AAAA-MM-JJ)")
    args = ap.parse_args()

    from apps.api.snapshot import _seed_universe, fetch_financials_chain
    from packages.reporting import (build_company_report, company_report_html,
                                    company_report_markdown, company_report_pdf)

    vault_dir = Path(os.environ.get("QUANT_VAULT", ROOT / "vault")) / "04_Companies"

    targets = ([t.strip().upper() for t in args.tickers.split(",") if t.strip()]
               if args.tickers else _targets(args.top))
    if not targets:
        print("aucun titre cible."); return 0

    out_dir = Path(args.out) if args.out else (ROOT / "out" / "notes" / date.today().isoformat())
    out_dir.mkdir(parents=True, exist_ok=True)
    names = {m.get("symbol"): m.get("name") for m in _seed_universe()}

    ok = 0
    for sym in targets:
        try:
            f, prior, _src = fetch_financials_chain(sym)
            if f is None:
                print(f"  {sym:<8} ⨯ aucune donnée"); continue
            r = build_company_report(f, name=names.get(sym, sym), prior=prior)
            (out_dir / f"note_{sym}.html").write_text(company_report_html(r), encoding="utf-8")
            company_report_pdf(r, out_dir / f"note_{sym}.pdf")     # PDF si reportlab, sinon HTML
            try:                                                   # note Obsidian qualitative (coffre)
                vault_dir.mkdir(parents=True, exist_ok=True)
                (vault_dir / f"{sym}.md").write_text(company_report_markdown(r), encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
            ok += 1
            print(f"  {sym:<8} ✓ note générée")
        except Exception as e:  # noqa: BLE001
            print(f"  {sym:<8} ⨯ {e}")
    print(f"{ok}/{len(targets)} notes → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
