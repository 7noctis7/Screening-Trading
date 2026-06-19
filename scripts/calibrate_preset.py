"""Calibration du preset sur TES données : meilleure combo (vol/DD/top-K/bande) par Sharpe déflaté.

  export QUANT_PRICE_DB=/chemin/YAHOO.db   # sinon synthétique
  python scripts/calibrate_preset.py

Anti-surapprentissage : le DSR pénalise le nombre d'essais. Un DSR ~0 partout = pas d'edge robuste.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from apps.api.snapshot import (_HISTORY_DAYS, _fundamentals_section, _load_prices,
                                   _seed_universe, _sector_of, datetime, timedelta, timezone)
    from packages.backtest.calibrate import calibrate_preset

    instruments = _seed_universe()
    sector_of = {m["symbol"]: _sector_of(m) for m in instruments}
    acmap = {m["symbol"]: m.get("asset_class", "equity") for m in instruments}
    names = {m["symbol"]: m.get("name", m["symbol"]) for m in instruments}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    print("Chargement des prix…")
    data, mode, _real = _load_prices(instruments, sector_of, end - timedelta(days=_HISTORY_DAYS), end, 7)
    print(f"Mode : {mode} · univers {len(data)}")
    import os as _os
    if mode.startswith("synthetic") and _os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print("\n⛔ DONNÉES SYNTHÉTIQUES — calibration non significative (DSR≈0 par construction).")
        print("   Branche QUANT_PRICE_DB, ou QUANT_ALLOW_SYNTHETIC=1 pour forcer la démo.")
        return
    print("Scores qualité (fondamentaux)…")
    fs = _fundamentals_section(list(data), acmap, names, sector_of, data)
    quality = {r["symbol"]: r.get("combined_score") for r in fs.get("rows", [])}

    print("Calibration (grille DD × top-K × bande)…\n")
    res = calibrate_preset(data, quality, asset_classes=acmap)
    if not res.get("available"):
        print("Indisponible (échantillon insuffisant)."); return

    b = res["best"]
    print(f"{res['n_trials']} combos testées · pas {res['step_days']} j\n")
    print(f"  {'DD-cible':>8s} {'top-K':>6s} {'bande':>6s} {'CAGR':>7s} {'Sharpe':>7s} "
          f"{'Sharpe défl.':>12s} {'maxDD':>7s} {'turnover':>9s}")
    for r in res["results"][:12]:
        mark = "  ⭐" if r is b else "    "
        print(f"{mark}{r['dd_target']*100:6.0f}% {r['top_k']:6d} {r['band']*100:5.0f}% "
              f"{r['cagr']*100:6.1f}% {r['sharpe']:7.2f} {r['dsr']*100:11.0f}% "
              f"{r['max_drawdown']*100:6.1f}% {r['turnover_annual']:8.2f}×")
    print(f"\n→ Meilleure combo : DD-cible {b['dd_target']*100:.0f}% · top-K {b['top_k']} · "
          f"bande {b['band']*100:.0f}% (Sharpe déflaté {b['dsr']*100:.0f}%).")
    print(f"  Pour l'appliquer : export QUANT_DD_TARGET={b['dd_target']}")
    print(f"\n{res['note']}")


if __name__ == "__main__":
    main()
