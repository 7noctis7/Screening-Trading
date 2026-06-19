"""Balayage « cœur indiciel + satellite preset » : quelle part de cœur (ETF passif) mélangée
au preset maximise la performance ? Affiche le tableau complet et la part RETENUE (adoptée
seulement si elle bat le preset pur).

SOURCE DE VÉRITÉ UNIQUE : on lit le résultat directement depuis build_snapshot() — c'est la
MÊME mesure que le site (preset de production, classé par qualité, fenêtre identique). Ainsi le
script et le dashboard ne peuvent JAMAIS diverger.

  export QUANT_PRICE_DB=/chemin/YAHOO.db
  python scripts/index_core_sweep.py                 # cœur QQQ (Nasdaq 100) par défaut
  python scripts/index_core_sweep.py --symbol SPY    # cœur S&P 500
  python scripts/index_core_sweep.py --core 0.5      # force/teste une part fixe
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default=None, help="ETF cœur (QQQ=Nasdaq 100, SPY=S&P 500)")
    ap.add_argument("--core", default=None, help="force une part de cœur ∈ [0,1] (sinon auto)")
    a = ap.parse_args()
    if a.symbol:
        os.environ["QUANT_INDEX_CORE_SYMBOL"] = a.symbol.upper()
    if a.core is not None:
        os.environ["QUANT_INDEX_CORE"] = str(a.core)

    print("Construction du snapshot (preset de production réel)… ~30-60 s\n")
    from apps.api.snapshot import build_snapshot
    d = build_snapshot()["dashboard"]
    ic = d.get("index_core", {})
    if not ic.get("table"):
        print("Cœur indiciel indisponible (données réelles d'indice absentes)."); return

    sym = ic.get("symbol", "QQQ")
    print(f"Cœur {sym} ({'réel' if ic.get('core_is_real') else 'repli synthétique'}) · "
          f"objectif {ic.get('objective', 'sharpe')}\n")
    print(f"  {'Cœur '+sym:>10s} {'Preset':>8s} {'CAGR':>8s} {'Sharpe':>7s} "
          f"{'Sortino':>8s} {'maxDD':>8s} {'Calmar':>7s} {'Rdt tot.':>9s}")
    for row in ic["table"]:
        s = row["stats"]
        if not s.get("available"):
            continue
        c = row["core"]
        mark = "  ◀ adopté" if ic.get("enabled") and abs(c - ic.get("core_pct", 0)) < 1e-6 else ""
        print(f"  {c*100:8.0f}% {(1-c)*100:7.0f}% {s['cagr']*100:7.1f}% {s['sharpe']:7.2f} "
              f"{s['sortino']:8.2f} {s['max_drawdown']*100:7.1f}% {s['calmar']:7.2f} "
              f"{s['total_return']*100:8.1f}%{mark}")
    print()
    base = ic.get("base_stats", {})
    if ic.get("enabled"):
        cp = ic["core_pct"]
        bs = ic.get("best_stats", {})
        how = "forcé (QUANT_INDEX_CORE)" if ic.get("manual") else "auto (meilleur Sharpe qui bat le preset pur)"
        print(f"  ✅ RETENU : {cp*100:.0f}% {sym} + {(1-cp)*100:.0f}% preset · {how}")
        print(f"     Sharpe {bs.get('sharpe')} vs preset pur {base.get('sharpe')} · "
              f"CAGR {bs.get('cagr', 0)*100:.1f}% · maxDD {bs.get('max_drawdown', 0)*100:.1f}%")
        print("     → déjà actif dans le dashboard et l'allocation de production.")
    else:
        print(f"  ⛔ Aucun mélange ne bat le preset pur (Sharpe {base.get('sharpe')}) "
              f"→ on reste à 100% preset.")
        print(f"     Pour tester quand même une part fixe :  python scripts/index_core_sweep.py --core 0.5")
    print("\n  ⚠️ Rééq. quotidien (turnover indicatif). Sans frais de mélange explicites.")


if __name__ == "__main__":
    main()
