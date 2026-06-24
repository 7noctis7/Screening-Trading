"""make kill-check — kill-switch INTRADAY (cron N×/jour) : ferme le trou de gap 24/7.

La stratégie rebalance en daily → un krach intraday (surtout crypto 24/7) n'est vu
qu'au prochain run. Ce check lit la courbe d'équité réelle (Alpaca+Bitmart) du snapshot
et alerte si le drawdown depuis le pic dépasse le seuil. Aplatissement RÉEL délégué au
kill-switch de `run_live.py --live` — aucun ordre ici : on décide et on alerte.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import os

    from packages.portfolio.stress import drawdown_breach

    limit = float(os.environ.get("QUANT_INTRADAY_DD", "-0.15"))
    try:
        from apps.api.snapshot import build_snapshot
        rp = build_snapshot()["dashboard"].get("real_portfolio") or {}
        curve = [p.get("v") for p in (rp.get("curve") or rp.get("equity") or [])]
        curve = [x for x in curve if isinstance(x, (int, float))]
    except Exception as e:  # noqa: BLE001
        print(f"⚠ courbe réelle indisponible ({e}) — check ignoré (best-effort).")
        return 0
    out = drawdown_breach(curve, dd_limit=limit)
    if not out.get("available"):
        print("ℹ Historique réel trop court — pas de check.")
        return 0
    print(f"Drawdown courant {out['drawdown']*100:.1f}% (pic {out['peak']}, "
          f"dernier {out['last']}) · seuil {limit*100:.0f}%")
    if out["breach"]:
        print("🔴 BREACH → aplatir : python3 scripts/run_live.py --live --yes "
              "(le kill-switch réduit l'exposition à 0).")
        return 2
    print("🟢 OK — sous le seuil.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
