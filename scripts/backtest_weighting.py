"""Backtest comparatif des PONDÉRATIONS (équipondéré / inverse-vol / min-var / risk-parity).

  python scripts/backtest_weighting.py                 # bande de non-trading 0 (rebalance complet)
  python scripts/backtest_weighting.py --band 0.03     # réduit le turnover (no-trade band 3%)
  python scripts/backtest_weighting.py --step 63       # rebalance trimestriel (turnover plus bas)

Montre le couple rendement/risque et le **turnover** de chaque schéma, NET de frais, point-in-time.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest comparatif des pondérations")
    ap.add_argument("--assets", type=int, default=120)
    ap.add_argument("--step", type=int, default=21)
    ap.add_argument("--band", type=float, default=0.0, help="bande de non-trading (ex. 0.03)")
    a = ap.parse_args()

    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _seed_universe, _sector_of,
                                   datetime, timedelta, timezone)
    from packages.backtest.weighting_backtest import weighting_backtest

    instruments = _seed_universe()
    sector_of = {m["symbol"]: _sector_of(m) for m in instruments}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    data, mode = _load_prices(instruments, sector_of, end - timedelta(days=_HISTORY_DAYS), end, 7)
    print(f"Mode des données : {mode} · univers {len(data)}")
    r = weighting_backtest(data, step=a.step, max_assets=a.assets, band=a.band)
    if not r.get("available"):
        print("Indisponible (échantillon insuffisant)."); return
    print(f"\n{r['n_rebalances']} rebalancements · {r['n_assets']} actifs · pas {r['step_days']} j "
          f"· bande {r['band']*100:.0f}% · frais {r['cost_bps']:.0f}bps (net)\n")
    print(f"  {'Pondération':22s} {'CAGR':>8s} {'Sharpe':>7s} {'Sharpe défl.':>12s} {'maxDD':>8s} {'turnover/an':>12s}")
    for name, m in r["schemes"].items():
        if not m.get("available"):
            continue
        print(f"  {name:22s} {m['cagr']*100:7.1f}% {m['sharpe']:7.2f} {m['dsr']*100:11.0f}% "
              f"{m['max_drawdown']*100:7.1f}% {m['turnover_annual']:11.2f}×")
    fr = r.get("leverage_frontier", [])
    if fr:
        print(f"\n  Frontière de LEVIER (meilleur schéma : {r['best_scheme']}) — le vrai prix du rendement :")
        print(f"    {'levier':>7s} {'CAGR':>8s} {'maxDD':>8s}   ruine ?")
        for f in fr:
            print(f"    {f['leverage']:6.1f}× {f['cagr']*100:7.1f}% {f['max_drawdown']*100:7.1f}%   "
                  f"{'⚠️ OUI' if f['ruin'] else 'non'}")
        print("    → viser un CAGR élevé exige du levier → drawdowns profonds et risque de ruine. À doser selon TA tolérance.")
    print("\n→ Cherche le meilleur Sharpe / la plus faible perte max au turnover le plus bas. "
          "La bande de non-trading (--band) réduit le turnover ; --step 63 = trimestriel.")
    out = ROOT / "out"; out.mkdir(exist_ok=True)
    (out / "backtest_weighting.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"Rapport : {out / 'backtest_weighting.json'}")


if __name__ == "__main__":
    main()
