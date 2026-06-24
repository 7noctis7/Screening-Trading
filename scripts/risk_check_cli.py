"""make risk-check — exposition brute recommandée vu l'état réel du marché.

Connecte les briques de risque (drawdown courant + vol prévue EWMA) en UN levier :
combien d'exposition tenir maintenant ? C'est l'edge prouvé du projet (gestion du
risque), pas un signal directionnel. Proxy béta par défaut = QQQ (cœur 50% QQQ).

  make risk-check
  make risk-check ARGS="--symbol SPY --target-vol 0.12 --dd-hard -0.25"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import numpy as np

    from packages.data.price_loader import load_bars
    from packages.portfolio.risk_overlay import recommended_exposure

    ap = argparse.ArgumentParser(description="Exposition recommandée (overlay risque)")
    ap.add_argument("--symbol", default="QQQ", help="proxy béta du cœur")
    ap.add_argument("--target-vol", type=float, default=0.10)
    ap.add_argument("--dd-soft", type=float, default=-0.10)
    ap.add_argument("--dd-hard", type=float, default=-0.20)
    ap.add_argument("--max-frac", type=float, default=1.0)
    a = ap.parse_args()

    bars = load_bars(a.symbol, years=3)
    if len(bars) < 60:
        print(f"❌ pas assez de prix pour {a.symbol} ({len(bars)}).")
        return 1
    closes = np.array([b.close for b in bars], float)
    rets = closes[1:] / closes[:-1] - 1.0
    res = recommended_exposure(rets, target_vol=a.target_vol, dd_soft=a.dd_soft,
                               dd_hard=a.dd_hard, max_frac=a.max_frac)
    if not res.get("available"):
        print(f"❌ série trop courte ({res.get('n', 0)}).")
        return 1

    print(f"\nOverlay de risque · {a.symbol} · cible vol {a.target_vol*100:.0f}%")
    print(f"  drawdown courant : {res['drawdown']*100:+.1f}%")
    print(f"  vol réalisée     : {res['realized_vol']*100:.1f}%")
    print(f"  vol prévue (EWMA): {res['forecast_vol']*100:.1f}%  "
          f"(retenue : {res['vol_used']*100:.1f}%)")
    print(f"  taper drawdown   : ×{res['dd_taper']:.2f}")
    print(f"  fraction vol     : ×{res['vol_fraction']:.2f}")
    print(f"  → EXPOSITION RECOMMANDÉE : {res['exposure']*100:.0f}%")
    if res["exposure"] < 0.5:
        print("  ⚠ DÉ-RISQUER : drawdown et/ou vol élevés → réduire la voile.")
    elif res["exposure"] >= 0.95:
        print("  ✅ Régime calme : exposition pleine justifiée.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
