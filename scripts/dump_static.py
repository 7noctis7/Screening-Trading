#!/usr/bin/env python3
"""Fige les payloads de l'API en JSON statiques + les notes d'analyse HTML, pour l'export Next.js
(GitHub Pages, parité avec `make start`). Écrit dans apps/web/public/{data,reports}.

  python scripts/dump_static.py [--max-reports 200]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PUB = ROOT / "apps" / "web" / "public"
DATA = PUB / "data"
REPORTS = PUB / "reports"
BP = os.environ.get("NEXT_PUBLIC_BASE_PATH", "")


def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except Exception:  # noqa: BLE001
        pass
    return str(o)


def _write(name: str, payload) -> None:
    (DATA / f"{name}.json").write_text(json.dumps(payload, default=_json_default, ensure_ascii=False),
                                       encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-reports", type=int, default=200)
    args = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    from apps.api import main as M
    print("Construction du snapshot (une fois, mis en cache)…")
    M._snap()

    # 1) endpoints sans paramètre → JSON figés (fidèles aux transformations des routes)
    routes = {
        "meta": M.meta, "dashboard": M.dashboard, "screener": M.screener,
        "preset_ledger": M.preset_ledger, "portfolio": M.portfolio, "positions": M.positions,
        "trades": M.trades, "sentiment": M.sentiment, "fundamentals": M.fundamentals,
        "universe": M.universe, "data": M.data, "themes": M.themes, "ml": M.ml,
        "live": M.live, "conviction": M.conviction, "investors": M.investors,
        "macro": M.macro, "events": M.events, "analytics": M.analytics,
    }
    for name, fn in routes.items():
        try:
            _write(name, fn())
            print(f"  ✓ data/{name}.json")
        except Exception as e:  # noqa: BLE001
            _write(name, {"available": False, "error": str(e)})
            print(f"  ⚠ data/{name}.json ({e})")
    _write("overlays", {})                       # overlays dynamiques neutralisés en statique

    # 2) notes d'analyse HTML par société (univers mobile), + listing data/notes.json
    from packages.reporting import company_report_html
    syms: list[str] = []
    cfg = ROOT / "config" / "mobile_universe.csv"
    if cfg.exists():
        with cfg.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                ac = (r.get("asset_class") or "").lower()
                if r.get("symbol") and ac in ("equity", "etf", ""):
                    syms.append(r["symbol"].strip())
    syms = syms[: args.max_reports]
    notes = []
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    for i, sym in enumerate(syms, 1):
        try:
            report, err = M._build_company_report_cached(sym)
            if not report:
                continue
            (REPORTS / f"{sym}.html").write_text(company_report_html(report, theme="dark"),
                                                 encoding="utf-8")
            notes.append({"date": today, "symbol": sym, "html": f"{BP}/reports/{sym}.html"})
            if i % 25 == 0:
                print(f"  … {i}/{len(syms)} notes")
        except Exception:  # noqa: BLE001
            continue
    _write("notes", {"available": bool(notes), "dates": [today] if notes else [], "notes": notes})
    print(f"✅ {len(notes)} notes HTML + {len(routes)+2} JSON → {PUB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
