"""Backtest « top-N méga-caps avec rotation sur le classement » vs S&P 500 / Nasdaq 100 (réels).

  export QUANT_PRICE_DB=/chemin/YAHOO.db
  python scripts/backtest_megacap.py            # top-10 par défaut, rebalance trimestriel

Répond à : « quelle perf en détenant les 10 plus grosses sociétés, rééquilibrées quand le
classement change ? ». Proxy de taille = dollar-volume (la cap historique est indisponible).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--step", type=int, default=63, help="jours entre rééquilibrages (63=trimestre)")
    a = ap.parse_args()

    from apps.api.snapshot import (_HISTORY_DAYS, _index_closes, _load_prices, _sector_of,
                                   _seed_universe, datetime, timedelta, timezone)
    from packages.backtest.conviction_backtest import _stats
    from packages.backtest.megacap import megacap_rotation
    import numpy as np

    inst = _seed_universe()
    so = {m["symbol"]: _sector_of(m) for m in inst}
    ac = {m["symbol"]: m.get("asset_class", "equity") for m in inst}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=_HISTORY_DAYS)
    data, mode, _real = _load_prices(inst, so, start, end, 7)
    print(f"Mode : {mode} · univers {len(data)} · top {a.top} · pas {a.step} j\n")

    r = megacap_rotation(data, asset_classes=ac, top_n=a.top, step=a.step)
    if not r.get("available"):
        print("Indisponible (échantillon insuffisant)."); return

    def _bench(aliases, syn):
        px, _ = _index_closes(aliases, start, end, syn)
        px = np.asarray(px, float)
        if px.size < a.step * 4:
            return None
        rr = [px[min(t + a.step, len(px) - 1)] / px[t] - 1 for t in range(0, len(px) - 1, a.step)]
        return _stats(rr, 252.0 / a.step)

    sp = _bench(["^GSPC", "SPY"], [])
    ndx = _bench(["^NDX", "^IXIC", "QQQ"], [])
    print(f"  {'Stratégie':28s} {'CAGR':>8s} {'Sharpe':>7s} {'maxDD':>8s} {'Rdt tot.':>9s}")
    s = r["stats"]
    print(f"  {'Top-'+str(a.top)+' méga-caps (rotation)':28s} {s['annualized']*100:7.1f}% {s['sharpe']:7.2f} "
          f"{s['max_drawdown']*100:7.1f}% {s['total_return']*100:8.1f}%")
    for name, st in (("S&P 500 (réel)", sp), ("Nasdaq 100 (réel)", ndx)):
        if st and st.get("available"):
            print(f"  {name:28s} {st['annualized']*100:7.1f}% {st['sharpe']:7.2f} "
                  f"{st['max_drawdown']*100:7.1f}% {st['total_return']*100:8.1f}%")
    print(f"\n  Rotation : {r['n_rebalances']} rééquilibrages · turnover {r['turnover_per_rebal']*100:.0f}%/rebal")
    print(f"  Top actuel : {', '.join(r['current_top'])}")
    print("\n  ⚠️ Proxy de taille = dollar-volume (la cap boursière historique n'est pas dans la base). "
          "Sans biais du survivant non corrigé → lire comme indicatif.")


if __name__ == "__main__":
    main()
