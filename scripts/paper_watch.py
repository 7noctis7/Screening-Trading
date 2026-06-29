"""make paper-watch — alerte si la perf paper RÉELLE dérive du backtest (cron nocturne).

Déterministe : courbe d'equity Alpaca (paper) → `perf_summary` → comparaison aux bornes
du backtest preset (lues au ledger). exit≠0 si dérive → le cron peut notifier. Idéal en
phase d'attente (track record avant capital réel) : on sait en J+1, pas dans 6 semaines.

  make paper-watch
  make paper-watch ARGS="--ref-sharpe 2.35 --ref-maxdd -0.048 --sharpe-drop 1.0"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _paper_equity() -> list[float]:
    """Courbe d'equity paper RÉELLE (Alpaca portfolio_history). [] si indispo."""
    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        hist = AlpacaBroker(paper=True).portfolio_history()
        return [float(p["v"]) for p in hist if p.get("v")]
    except Exception:  # noqa: BLE001 - best-effort (clés absentes / hors-ligne)
        return []


def _ref_from_ledger() -> dict:
    """Bornes backtest = dernier `preset` du ledger (sharpe, max_drawdown)."""
    try:
        from packages.research.ledger import read_records
        presets = [r for r in read_records() if r.get("facteur") == "preset"]
        if presets:
            last = presets[-1]
            return {"sharpe": last.get("sharpe"), "max_drawdown": last.get("maxdd")}
    except Exception:  # noqa: BLE001
        pass
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="Watchdog dérive paper vs backtest")
    ap.add_argument("--ref-sharpe", type=float, default=None)
    ap.add_argument("--ref-maxdd", type=float, default=None)
    ap.add_argument("--sharpe-drop", type=float, default=1.0)
    ap.add_argument("--dd-buffer", type=float, default=0.05)
    ap.add_argument("--min-obs", type=int, default=20)
    a = ap.parse_args()

    from packages.portfolio.paper_watch import drift_report
    ref = _ref_from_ledger()
    if a.ref_sharpe is not None:
        ref["sharpe"] = a.ref_sharpe
    if a.ref_maxdd is not None:
        ref["max_drawdown"] = a.ref_maxdd

    equity = _paper_equity()
    if not equity:
        print("paper indisponible (Alpaca non configuré / hors-ligne) — rien à voir.")
        return 0
    if not ref:
        print("⚠ pas de réf backtest (ledger vide) — passe --ref-sharpe/--ref-maxdd.")
        return 0

    res = drift_report(equity, ref, sharpe_drop=a.sharpe_drop,
                       dd_buffer=a.dd_buffer, min_obs=a.min_obs)
    if not res.get("available"):
        print(f"track record paper trop court ({res['n']}/{res['min_obs']} jours) — "
              "le watchdog s'activera en grandissant.")
        return 0

    p = res["paper"]
    print(f"\nPaper-watch · {p['n']} jours · Sharpe {p['sharpe']} · MaxDD "
          f"{p['max_drawdown']*100:+.1f}% · CAGR {p['cagr']*100:+.1f}%")
    print(f"  référence backtest : {ref}")
    if res["drift"]:
        print("  → ⚠ DÉRIVE DÉTECTÉE :")
        for al in res["alerts"]:
            print(f"     - {al}")
        print("  ACTION : ne pas engager de capital réel ; ré-examiner le preset.")
        return 1                                            # exit≠0 → le cron notifie
    print("  → ✅ paper conforme au backtest (aucune dérive).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
