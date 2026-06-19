"""Backtest comparatif ML walk-forward (point-in-time, gratuit) — script OFFLINE.

  python scripts/backtest_ml.py            # données réelles si QUANT_PRICE_DB, sinon synthétique
  python scripts/backtest_ml.py --assets 200 --step 21

Compare : conviction+ML vs conviction technique vs équipondéré (rendement, Sharpe, Sharpe
déflaté, max DD, turnover). Écrit aussi out/backtest_ml.json. Lourd (ré-entraînement) → patience.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest ML walk-forward (point-in-time)")
    ap.add_argument("--assets", type=int, default=150)
    ap.add_argument("--step", type=int, default=21)
    a = ap.parse_args()

    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _seed_universe, _sector_of,
                                   datetime, timedelta, timezone)
    from packages.backtest.ml_walkforward import ml_walkforward

    instruments = _seed_universe()
    sector_of = {m["symbol"]: _sector_of(m) for m in instruments}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=_HISTORY_DAYS)
    data, mode, _real = _load_prices(instruments, sector_of, start, end, 7)
    print(f"Mode des données : {mode} · univers {len(data)}")
    print("Backtest ML walk-forward en cours (ré-entraînement à chaque rebalancement)…")
    res = ml_walkforward(data, step=a.step, max_assets=a.assets)
    if not res.get("available"):
        print("Backtest indisponible (échantillon insuffisant)."); return

    def line(label, m):
        if not m.get("available"):
            return f"  {label:28s} —"
        return (f"  {label:28s} rendement {m['total_return']*100:7.1f}%  ann. {m['annualized']*100:6.1f}%  "
                f"Sharpe {m['sharpe']:5.2f}  Sharpe déflaté {m['dsr']*100:4.0f}%  maxDD {m['max_drawdown']*100:6.1f}%")

    print(f"\n{res['n_rebalances']} rebalancements · {res['n_assets']} actifs · pas {res['step_days']} j "
          f"· turnover {res['turnover_annual']}×/an\n")
    print(line("Conviction + ML (brut)", res["ml"]))
    print(line(f"Conviction + ML (net {res['cost_bps']:.0f}bps)", res["ml_net"]))
    print(line("Conviction technique", res["tech"]))
    print(line("Équipondéré (benchmark)", res["benchmark"]))
    it, im = res["ic_tech"], res["ic_ml"]
    print(f"\n  Information Coefficient (pouvoir prédictif du signal) :")
    print(f"    technique : IC {it['ic_mean']:+.3f} (t={it['ic_tstat']:+.1f})   "
          f"ML : IC {im['ic_mean']:+.3f} (t={im['ic_tstat']:+.1f})")
    print("    Repère : |IC|~0 = aucun pouvoir prédictif ; |t|>2 = significatif. Un bon facteur fait IC 0.03–0.06.")
    print("\n→ Sharpe déflaté >0 ET > bench = edge crédible. IC≈0 ⇒ signal sans info ⇒ ne pas déployer.")

    out = ROOT / "out"; out.mkdir(exist_ok=True)
    (out / "backtest_ml.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nRapport écrit : {out / 'backtest_ml.json'}")


if __name__ == "__main__":
    main()
