"""Balayage « cœur indiciel + satellite preset » : quelle part de cœur (ETF passif) mélangée
au preset maximise la performance ? Affiche le tableau complet et la part RETENUE (adoptée
seulement si elle bat le preset pur).

  export QUANT_PRICE_DB=/chemin/YAHOO.db
  python scripts/index_core_sweep.py                 # cœur QQQ (Nasdaq 100) par défaut
  python scripts/index_core_sweep.py --symbol SPY    # cœur S&P 500
  python scripts/index_core_sweep.py --objective calmar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="QQQ", help="ETF cœur (QQQ=Nasdaq 100, SPY=S&P 500)")
    ap.add_argument("--objective", default="sharpe", choices=["sharpe", "cagr", "calmar", "sortino"])
    a = ap.parse_args()

    from apps.api.snapshot import (_HISTORY_DAYS, _index_closes, _load_prices, _sector_of,
                                   _seed_universe, datetime, timedelta, timezone)
    from packages.backtest.index_core import optimize_index_core
    from packages.backtest.preset_backtest import preset_equity_daily

    inst = _seed_universe()
    so = {m["symbol"]: _sector_of(m) for m in inst}
    ac = {m["symbol"]: m.get("asset_class", "equity") for m in inst}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=_HISTORY_DAYS)
    data, mode = _load_prices(inst, so, start, end, 7)

    # preset équités uniquement (mêmes filtres que la production)
    tradeable = {s: b for s, b in data.items()
                 if ac.get(s, "equity") in ("equity", "etf")}
    pe = preset_equity_daily(tradeable, None, asset_classes=ac, dd_target=0.35)
    if not pe.get("available"):
        print("Preset indisponible (échantillon insuffisant)."); return

    sym = a.symbol.upper()
    aliases = [sym] + (["^NDX", "^IXIC"] if sym == "QQQ" else ["^GSPC", "SPX"] if sym == "SPY" else [])
    core, core_real = _index_closes(aliases, start, end, [])
    if not core or len(core) < 60:
        print(f"Cœur {sym} indisponible (pas de données réelles)."); return

    r = optimize_index_core(pe["equity"], core, grid=(0.0, 0.25, 0.5, 0.75, 1.0),
                            objective=a.objective)
    print(f"Mode données : {mode} · cœur {sym} ({'réel' if core_real else 'repli'}) · "
          f"objectif {a.objective}\n")
    print(f"  {'Cœur '+sym:>10s} {'Preset':>8s} {'CAGR':>8s} {'Sharpe':>7s} "
          f"{'Sortino':>8s} {'maxDD':>8s} {'Calmar':>7s} {'Rdt tot.':>9s}")
    for row in r["table"]:
        s = row["stats"]
        if not s.get("available"):
            continue
        c = row["core"]
        print(f"  {c*100:8.0f}% {(1-c)*100:7.0f}% {s['cagr']*100:7.1f}% {s['sharpe']:7.2f} "
              f"{s['sortino']:8.2f} {s['max_drawdown']*100:7.1f}% {s['calmar']:7.2f} "
              f"{s['total_return']*100:8.1f}%")
    print()
    if r["improved"]:
        bc, bs = r["best_core"], r["best_stats"]
        print(f"  ✅ RETENU : {bc*100:.0f}% {sym} + {(1-bc)*100:.0f}% preset "
              f"(Sharpe {bs['sharpe']:.2f} vs preset pur {r['base_stats']['sharpe']:.2f}, "
              f"CAGR {bs['cagr']*100:.1f}%, maxDD {bs['max_drawdown']*100:.1f}%).")
        print(f"     → active en prod :  export QUANT_INDEX_CORE={bc}")
    else:
        print(f"  ⛔ Aucun mélange ne bat le preset pur sur {a.objective} → on reste à 100% preset.")
    print("\n  ⚠️ Rééq. quotidien (turnover indicatif). Sans frais de mélange explicites.")


if __name__ == "__main__":
    main()
