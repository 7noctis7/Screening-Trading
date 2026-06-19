"""Backtest des cassures Donchian + measure rule (Bulkowski) — script offline, point-in-time.

  python scripts/backtest_breakout.py --lookback 20 --hold 21

Honnête : on n'intègre la cassure comme signal QUE si t-stat > 2 ET edge vs marché > 0.
Sinon, on garde seulement la "measure rule" comme objectif de sortie.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest cassures Donchian + measure rule")
    ap.add_argument("--lookback", type=int, default=20)
    ap.add_argument("--hold", type=int, default=21)
    ap.add_argument("--assets", type=int, default=200)
    a = ap.parse_args()

    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _seed_universe, _sector_of,
                                   datetime, timedelta, timezone)
    from packages.backtest.breakout_backtest import breakout_backtest

    instruments = _seed_universe()
    sector_of = {m["symbol"]: _sector_of(m) for m in instruments}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    data, mode, _real = _load_prices(instruments, sector_of, end - timedelta(days=_HISTORY_DAYS), end, 7)
    syms = list(data)[:a.assets]
    print(f"Mode des données : {mode} · {len(syms)} actifs")
    r = breakout_backtest({s: data[s] for s in syms}, lookback=a.lookback, hold=a.hold)
    if not r.get("available"):
        print(f"Indisponible ({r.get('n_events', 0)} cassures)."); return
    print(f"\n  Cassures Donchian {r['lookback']}j · sortie {r['hold']}j ({r['n_events']} évènements) :")
    print(f"    rendement moyen   {r['mean_return']*100:+.2f}%")
    print(f"    win rate          {r['win_rate']*100:.0f}%   (objectifs atteints {r['target_hits']} · stops {r['stop_hits']})")
    print(f"    t-stat            {r['t_stat']:+.2f}   (|t|>2 = significatif)")
    print(f"    edge vs marché    {r['edge_vs_market']*100:+.2f}%")
    # exigeant : un gros échantillon rend significatif un edge trivial → on veut un edge ÉCONOMIQUE
    ok = r["t_stat"] > 2 and r["edge_vs_market"] > 0.005
    if ok:
        print("\n→ ✅ Edge crédible ET économiquement significatif (>0.5% vs marché) → intégrable comme signal.")
    elif r["edge_vs_market"] <= 0.005 and r["mean_return"] > 0:
        print("\n→ ⚠️ Rendement positif mais edge vs marché négligeable (c'est du momentum, pas un edge distinct). "
              "Best practice : garder seulement la MEASURE RULE comme objectif de sortie.")
    else:
        print("\n→ ❌ Pas d'edge → garder seulement la measure rule comme objectif de sortie.")


if __name__ == "__main__":
    main()
