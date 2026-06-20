"""Rapport de performance QuantStats (Sortino/Calmar/Alpha/Beta vs QQQ) → coffre Obsidian.

  python scripts/perf_report.py     # écrit vault/Performance_Report.md depuis le snapshot (preset vs QQQ)

Best-effort : si la donnée manque, écrit une note explicite sans crash.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from packages.reporting.analytics import PerformanceAnalytics
    try:
        from apps.api.snapshot import build_snapshot
        snap = build_snapshot()
    except Exception as e:  # noqa: BLE001
        print(f"snapshot indisponible : {e}"); return
    cur = snap.get("index_core_curves", {}) or {}
    pa = PerformanceAnalytics.from_curves(cur.get("preset") or [], cur.get("qqq") or [])
    md = pa.to_markdown_summary("Preset — performance (net de frais) vs QQQ")
    out = ROOT / "vault" / "Performance_Report.md"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"écrit : {out}")
    except OSError as e:
        print(f"écriture impossible : {e}")
    print(pa.metrics().to_dict())


if __name__ == "__main__":
    main()
