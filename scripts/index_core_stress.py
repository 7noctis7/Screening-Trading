"""Stress-test BEAR du cœur indiciel + satellite : comment se comporte le portefeuille pendant
les krachs / marchés baissiers, selon la part de QQQ.

Identifie les pires épisodes de drawdown de QQQ (pic→creux) sur TES données réelles, puis chiffre,
pour chaque ratio (0 / 25 / 50 / 70 / 100 % QQQ + le reste preset), la perte subie pendant CES
épisodes + le maxDD global. Source de vérité unique : courbes de production (build_snapshot).

  export QUANT_PRICE_DB=/chemin/YAHOO.db
  export QUANT_HISTORY_DAYS=3650          # fenêtre longue (recommandé pour voir les vrais bears)
  python scripts/index_core_stress.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RATIOS = (0.0, 0.25, 0.50, 0.70, 1.0)


def _dd(curve):
    import numpy as np
    c = np.asarray(curve, float)
    return float((c / np.maximum.accumulate(c) - 1).min())


def _episodes(curve, k=3, min_dd=0.12):
    """Pires épisodes baissiers de `curve` : [{peak, trough, end, depth}] triés du + profond."""
    import numpy as np
    c = np.asarray(curve, float)
    dd = c / np.maximum.accumulate(c) - 1
    eps, i, n = [], 0, len(c)
    while i < n:
        if dd[i] < 0:
            j = i
            while j < n and dd[j] < 0:
                j += 1
            tr = i + int(np.argmin(dd[i:j]))
            depth = float(dd[tr])
            if depth <= -min_dd:
                eps.append({"peak": i - 1 if i > 0 else 0, "trough": tr, "end": j - 1, "depth": depth})
            i = j
        else:
            i += 1
    return sorted(eps, key=lambda e: e["depth"])[:k]


def main() -> None:
    import numpy as np
    print("Construction du snapshot (courbes réelles)… ~30-60 s\n")
    from apps.api.snapshot import build_snapshot
    cur = build_snapshot().get("index_core_curves", {})
    preset, qqq, dates = cur.get("preset", []), cur.get("qqq", []), cur.get("dates", [])
    if not preset or not qqq or len(qqq) < 200:
        print("QQQ ou preset indisponible (données réelles requises)."); return

    n = min(len(preset), len(qqq))
    p, q = np.asarray(preset[-n:], float), np.asarray(qqq[-n:], float)
    d = dates[-n:] if len(dates) >= n else [""] * n
    pr, qr = p[1:] / p[:-1] - 1, q[1:] / q[:-1] - 1

    def blend(ratio):                                  # courbe d'equity du mélange (rééq. quotidien)
        br = ratio * qr + (1 - ratio) * pr
        eq = [1.0]
        for r in br:
            eq.append(eq[-1] * (1 + r))
        return np.asarray(eq)

    blends = {r: blend(r) for r in RATIOS}
    eps = _episodes(q, k=3, min_dd=0.12)               # bears définis par QQQ (indice de référence)

    print(f"Fenêtre : {d[0][:10]} → {d[-1][:10]}  ({n} jours)\n")
    print("PERTE PIC→CREUX pendant les pires épisodes baissiers de QQQ (perte de TON portefeuille) :\n")
    hdr = "  " + "Épisode (pic→creux)".ljust(26) + "QQQ".rjust(8) + "".join(f"{int(r*100)}%QQQ".rjust(9) for r in RATIOS)
    print(hdr)
    for e in eps:
        pk, tr = e["peak"], e["trough"]
        qloss = q[tr] / q[pk] - 1
        cells = "".join(f"{(blends[r][tr]/blends[r][pk]-1)*100:8.1f}%" for r in RATIOS)
        lab = f"{d[pk][:10]}→{d[tr][:10]}"
        print(f"  {lab:26s}{qloss*100:7.1f}%{cells}")
    print("\nMAX DRAWDOWN GLOBAL par ratio (sur toute la fenêtre) :")
    print("  " + "".join(f"{int(r*100)}%QQQ".rjust(10) for r in RATIOS))
    print("  " + "".join(f"{_dd(blends[r])*100:9.1f}%" for r in RATIOS))
    print("\n  Lecture : plus la part QQQ est haute, plus la perte en bear est profonde (le preset")
    print("  vol-targeté amortit). À mettre en face du gain de rendement en bull (cf. make index-core).")


if __name__ == "__main__":
    main()
