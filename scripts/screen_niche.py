"""Screen d'EXPLOITABILITÉ d'un micro-marché (ticket #4) : décide si une niche vaut le coup AVANT
de s'y engager. Mesure autocorr / variance-ratio / dispersion / DSR momentum → score 0-100.

  # univers complet (seeds) :
  python scripts/screen_niche.py
  # une niche ciblée :
  export QUANT_UNIVERSE=$HOME/Screening-Trading/data/niche.csv
  export QUANT_PRICE_DB=$HOME/Desktop/YAHOO.db
  python scripts/screen_niche.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    import os
    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _seed_universe, _sector_of,
                                   datetime, timedelta, timezone)
    from packages.data.inefficiency import inefficiency_report

    inst = _seed_universe()
    so = {m["symbol"]: _sector_of(m) for m in inst}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    data, mode = _load_prices(inst, so, end - timedelta(days=_HISTORY_DAYS), end, 7)
    src = os.environ.get("QUANT_UNIVERSE", "seeds (univers complet)")
    print(f"Univers : {src}\nMode données : {mode} · {len(data)} actifs\n")

    r = inefficiency_report(data)
    if not r.get("available"):
        print(f"Indisponible : {r.get('reason')}"); return

    bar = "█" * int(r["score"] / 5) + "·" * (20 - int(r["score"] / 5))
    print(f"  SCORE D'EXPLOITABILITÉ : {r['score']}/100  [{bar}]")
    print(f"  VERDICT : {r['verdict']}\n")
    print(f"  Autocorrélation lag-1   : {r['autocorr_lag1']:+.4f}  (>0 = momentum persistant)")
    print(f"  Variance ratio (q=5)    : {r['variance_ratio']:.3f}   (≠1 = s'écarte du hasard)")
    print(f"  Dispersion cross-sec.   : {r['cross_dispersion']:.5f} (opportunité de sélection)")
    print(f"  Momentum Sharpe / DSR   : {r['momentum_sharpe']} / {r['momentum_dsr']*100:.0f}%  (edge réel)")
    print(f"\n  {r['note']}")
    if r["score"] < 25:
        print("\n  → Marché efficient : NE PAS s'engager (tu échangerais de la diversification "
              "contre du bruit). Cherche une niche plus inefficiente.")
    elif r["score"] < 50:
        print("\n  → Incertain : tester en walk-forward (make backtest-preset) avant de t'engager.")
    else:
        print("\n  → Edge potentiel : valide en walk-forward, puis concentre-toi sur cette niche.")


if __name__ == "__main__":
    main()
