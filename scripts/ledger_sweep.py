"""Sweep RÉALISTE : performance du journal discret (parts/cash, prix réels) selon les réglages —
part de QQQ × DD-target (exposition) × fréquence de rebalancement. Aide à choisir le couple
rendement/drawdown EN CONNAISSANCE DE CAUSE (chiffres exécutables, pas idéalisés).

  export QUANT_PRICE_DB=/chemin/YAHOO.db ; export QUANT_HISTORY_DAYS=4015
  python scripts/ledger_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

QQQ = [0.5, 0.7, 1.0]
DDS = [0.35, 0.45]
STEPS = {"hebdo": 5, "mensuel": 21, "trimestriel": 63}


def main() -> None:
    from apps.api.snapshot import (_HISTORY_DAYS, _index_closes, _load_prices, _sector_of,
                                   _seed_universe, datetime, timedelta, timezone)
    from packages.backtest.preset_backtest import preset_ledger
    from packages.backtest.index_core import _stats
    from packages.execution.routing import is_tradeable

    inst = _seed_universe()
    so = {m["symbol"]: _sector_of(m) for m in inst}
    ac = {m["symbol"]: m.get("asset_class", "equity") for m in inst}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=_HISTORY_DAYS)
    data, mode, real = _load_prices(inst, so, start, end, 7)
    td = {s: b for s, b in data.items() if is_tradeable(s, ac.get(s, "equity")) and (s in real or not real)}
    qqq, _ = _index_closes(["QQQ", "^NDX", "^IXIC"], start, end, [])
    print(f"Mode {mode} · {len(td)} titres négociables · cœur QQQ {'réel' if qqq else 'indispo'}\n")
    print("Chiffres RÉALISTES (journal discret parts/cash) — relatif fiable ; absolu indicatif.\n")

    def run(qpct, dd, step):
        L = preset_ledger(td, None, asset_classes=ac, dd_target=dd, step=step, init_cap=10000.0,
                          max_trades=1, core_closes=qqq if qpct > 0 else None, core_pct=qpct)
        if not L.get("available"):
            return None
        eq = L["equity"]
        r = [eq[i + 1] / eq[i] - 1 for i in range(len(eq) - 1)]
        return _stats(eq), L["summary"], r and len(r)

    print(f"  {'Réglage':34s}{'CAGR':>8s}{'Sharpe':>8s}{'maxDD':>8s}{'Rdt tot.':>10s}")
    for step_name, step in STEPS.items():
        for dd in DDS:
            for qp in QQQ:
                res = run(qp, dd, step)
                if not res:
                    continue
                st, sm, _ = res
                lab = f"{int(qp*100)}%QQQ · DD{int(dd*100)} · {step_name}"
                print(f"  {lab:34s}{st['cagr']*100:7.1f}%{st['sharpe']:8.2f}{st['max_drawdown']*100:7.1f}%"
                      f"{sm['total_return']*100:9.1f}%")
        print()
    print("⚠️ Plus de QQQ / DD-target élevé / rebalancement rare = + de rendement MAIS + de drawdown.")
    print("   Rebalancement fréquent (hebdo) = + de turnover/frais réels (non modélisés ici).")
    print("   Pour figer un réglage : export QUANT_CORE_SPEC=\"qqq:0.7\" et/ou QUANT_DD_TARGET=0.45")


if __name__ == "__main__":
    main()
