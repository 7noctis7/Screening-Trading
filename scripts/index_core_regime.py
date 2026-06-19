"""Allocation ADAPTATIVE AU RÉGIME (bull / range / bear) du cœur QQQ + satellite preset.

1) DÉTECTE le régime de marché à partir de la TENDANCE S&P 500 réelle (point-in-time, sans fuite) :
   - bull  : cours > MM200 ET MM200 en hausse ;
   - bear  : cours < MM200 ET MM200 en baisse ;
   - range : le reste (indécis / sans tendance).
2) Mesure, par régime, la meilleure part de QQQ (0/25/50/75/100 %) par Sharpe.
3) BACKTESTE une règle adaptative (bull→70 %, range→30 %, bear→0 % QQQ) et la compare au fixe
   50 % QQQ et au preset pur → la donnée dit si le market-timing améliore vraiment la perf.

Données 100 % réelles (build_snapshot). Aucune donnée fictive.

  export QUANT_PRICE_DB=/chemin/YAHOO.db
  export QUANT_HISTORY_DAYS=3650
  python scripts/index_core_regime.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Règle d'allocation adaptative par défaut (part de QQQ ; le reste = preset).
ADAPTIVE = {"bull": 0.70, "range": 0.30, "bear": 0.0}
RATIOS = (0.0, 0.25, 0.50, 0.75, 1.0)


def _stats(rets):
    import numpy as np
    r = np.asarray(rets, float)
    if r.size < 30:
        return {"cagr": 0, "sharpe": 0, "maxdd": 0}
    eq = np.cumprod(1 + r)
    cagr = float(eq[-1] ** (252.0 / r.size) - 1)
    sd = float(r.std())
    mdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    return {"cagr": cagr, "sharpe": (r.mean() / sd * 252 ** 0.5) if sd > 0 else 0.0, "maxdd": mdd}


def _sma(c, w):
    import numpy as np
    out = np.full(len(c), np.nan)
    if len(c) >= w:
        cs = np.cumsum(np.insert(c, 0, 0.0))
        out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


def detect_regime(sp):
    """Régime point-in-time par jour depuis la MM200 du S&P (et sa pente sur 20 j)."""
    import numpy as np
    c = np.asarray(sp, float)
    sma = _sma(c, 200)
    reg = []
    for t in range(len(c)):
        if t < 220 or np.isnan(sma[t]) or np.isnan(sma[t - 20]):
            reg.append("range"); continue
        above, rising = c[t] > sma[t], sma[t] > sma[t - 20]
        reg.append("bull" if (above and rising) else "bear" if (not above and not rising) else "range")
    return reg


def main() -> None:
    import numpy as np
    print("Construction du snapshot (courbes réelles)… ~30-60 s\n")
    from apps.api.snapshot import build_snapshot
    cur = build_snapshot().get("index_core_curves", {})
    preset, qqq, sp, dates = cur.get("preset", []), cur.get("qqq", []), cur.get("sp", []), cur.get("dates", [])
    if not (preset and qqq and sp) or min(len(preset), len(qqq), len(sp)) < 300:
        print("Données réelles (preset/QQQ/S&P) insuffisantes."); return

    n = min(len(preset), len(qqq), len(sp))
    p, q, s = np.asarray(preset[-n:], float), np.asarray(qqq[-n:], float), np.asarray(sp[-n:], float)
    d = dates[-n:] if len(dates) >= n else [""] * n
    pr, qr = p[1:] / p[:-1] - 1, q[1:] / q[:-1] - 1
    reg = detect_regime(s)[1:]                          # régime aligné sur les rendements (t→t+1)
    reg = np.asarray(reg)

    print(f"Fenêtre : {d[0][:10]} → {d[-1][:10]}\n")
    print("RÉPARTITION DU TEMPS PAR RÉGIME (détection MM200 S&P, point-in-time) :")
    for g in ("bull", "range", "bear"):
        print(f"  {g:6s}: {(reg == g).mean()*100:5.1f}% du temps")

    print("\nMEILLEURE PART DE QQQ PAR RÉGIME (Sharpe sur les jours du régime) :")
    print(f"  {'Régime':8s}{'0%':>8s}{'25%':>8s}{'50%':>8s}{'75%':>8s}{'100%':>8s}   meilleur")
    best_by = {}
    for g in ("bull", "range", "bear"):
        m = reg == g
        if m.sum() < 30:
            print(f"  {g:8s} (échantillon insuffisant)"); best_by[g] = ADAPTIVE[g]; continue
        sh = {}
        for r in RATIOS:
            br = r * qr[m] + (1 - r) * pr[m]
            sh[r] = _stats(br)["sharpe"]
        best = max(sh, key=sh.get)
        best_by[g] = best
        cells = "".join(f"{sh[r]:8.2f}" for r in RATIOS)
        print(f"  {g:8s}{cells}   {int(best*100)}% QQQ")

    # backtests plein-période : adaptatif (règle fixe), adaptatif (best in-sample), fixes, preset
    def run(weight_fn):
        br = np.array([weight_fn(reg[i]) * qr[i] + (1 - weight_fn(reg[i])) * pr[i] for i in range(len(pr))])
        return _stats(br)

    rows = [("Preset pur (0% QQQ)", _stats(pr)),
            ("Fixe 50% QQQ", _stats(0.5 * qr + 0.5 * pr)),
            ("Fixe 70% QQQ", _stats(0.7 * qr + 0.3 * pr)),
            ("Adaptatif (bull70/range30/bear0)", run(lambda g: ADAPTIVE[g])),
            ("Adaptatif (best par régime*)", run(lambda g: best_by[g]))]
    print("\nPERFORMANCE PLEINE PÉRIODE :")
    print(f"  {'Stratégie':34s}{'CAGR':>8s}{'Sharpe':>8s}{'maxDD':>9s}")
    for name, st in rows:
        print(f"  {name:34s}{st['cagr']*100:7.1f}%{st['sharpe']:8.2f}{st['maxdd']*100:8.1f}%")
    base = rows[1][1]                                   # fixe 50% = référence de production
    adp = rows[3][1]
    print()
    if adp["sharpe"] > base["sharpe"] + 0.05:
        print(f"  ✅ L'adaptatif AMÉLIORE le Sharpe ({adp['sharpe']:.2f} vs 50% fixe {base['sharpe']:.2f}).")
    else:
        print(f"  ⛔ L'adaptatif n'améliore PAS nettement (Sharpe {adp['sharpe']:.2f} vs 50% fixe {base['sharpe']:.2f}).")
    print("  *« best par régime » est optimisé in-sample → optimiste (à lire comme borne haute, pas une promesse).")
    print("  ⚠️ Rééq. quotidien, sans frais ni slippage de switch (le market-timing en a en vrai).")


if __name__ == "__main__":
    main()
