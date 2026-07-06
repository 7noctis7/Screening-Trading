#!/usr/bin/env python3
"""RDV paper 2026-08-06 — rapport GO/NO-GO mécanique (paper réel vs backtest preset).

  make rdv-paper          # sur le Mac (courbes réelles : equity_history + preset)

Charge la courbe PAPER réelle (suivi quotidien Alpaca, `equity_history`) et la courbe
MODÈLE (backtest preset sur la même fenêtre), applique les critères du vault via
`packages.research.rdv_paper.compare`, imprime le verdict et l'archive dans
`vault/10_Backtests/RDV_Paper.md`. Best-effort : données absentes → INSUFFISANT.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.research.rdv_paper import compare  # noqa: E402


def _paper_curve() -> tuple[list[str], list[float]]:
    """Courbe paper réelle (suivi quotidien du compte Alpaca). ([],[]) si vide."""
    from packages.execution.equity_history import series
    rows = series("Alpaca") or []
    rows = [r for r in rows if r.get("equity")]
    return [r["date"] for r in rows], [float(r["equity"]) for r in rows]


def _model_curve(dates: list[str]) -> list[float]:
    """Courbe MODÈLE (preset) restreinte à la fenêtre paper. [] si indisponible."""
    try:
        from apps.api.snapshot import build_snapshot
        snap = build_snapshot()
        eq = (snap.get("dashboard") or {}).get("equity") or []
        dts = (snap.get("dashboard") or {}).get("dates") or []
        by = {d[:10]: float(v) for d, v in zip(dts, eq) if v}
        return [by[d[:10]] for d in dates if d[:10] in by]
    except Exception as e:  # noqa: BLE001
        print(f"· courbe modèle indisponible ({str(e)[:60]})")
        return []


def _write_note(rep: dict) -> None:
    note = ROOT / "vault" / "10_Backtests" / "RDV_Paper.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"  - {c['name']} : {c['value']} → {'✅' if c['ok'] else '❌'}"
             for c in rep["criteria"]]
    note.write_text(f"""---
type: rdv_paper
date: {datetime.now(timezone.utc).date().isoformat()}
verdict: {rep['verdict']}
---
# RDV paper — verdict mécanique : **{rep['verdict']}**
> {rep['decision']}

- Sharpe paper {rep['sharpe_paper']} vs modèle {rep['sharpe_model']}
- MaxDD paper {rep['maxdd_paper']} vs modèle {rep['maxdd_model']}
- N = {rep['n_days_paper']} j · MinTRL = {rep['min_trl_days']} j
{chr(10).join(lines)}

*Critères figés au vault (03_TODO « RENDEZ-VOUS ») — le verdict est mécanique,
pas une humeur. Regénérer : `make rdv-paper`.*
""", encoding="utf-8")
    print(f"→ note archivée : {note.relative_to(ROOT)}")


def main() -> int:
    dates, paper = _paper_curve()
    if len(paper) < 2:
        print("INSUFFISANT — aucune courbe paper enregistrée (equity_history vide).")
        return 2
    model = _model_curve(dates)
    if len(model) < 2:
        print("INSUFFISANT — courbe modèle indisponible sur la fenêtre paper.")
        return 2
    rep = compare(paper, model)
    print(f"RDV PAPER — verdict : {rep['verdict']}  ({rep['decision']})")
    print(f"  Sharpe paper {rep['sharpe_paper']} vs modèle {rep['sharpe_model']} · "
          f"MaxDD {rep['maxdd_paper']} vs {rep['maxdd_model']} · "
          f"N={rep['n_days_paper']} j (MinTRL {rep['min_trl_days']})")
    for c in rep["criteria"]:
        print(f"  {'✅' if c['ok'] else '❌'} {c['name']} : {c['value']}")
    _write_note(rep)
    return 0 if rep["verdict"] == "GO" else 2 if rep["verdict"] == "INSUFFISANT" else 1


if __name__ == "__main__":
    sys.exit(main())
