"""Sweep « cœur(s) indiciel(s) + satellite preset » sur ta VRAIE data.

SOURCE DE VÉRITÉ UNIQUE : on construit le snapshot UNE fois (preset de production réel + courbes
QQQ et top-10 méga-caps), puis on balaie instantanément tous les ratios localement. Le script et
le site partagent donc exactement la même mesure.

  export QUANT_PRICE_DB=/chemin/YAHOO.db
  python scripts/index_core_sweep.py                 # sweeps QQQ et top-10 + blend configuré
  python scripts/ingest_market_cap.py                # (avant) pour pondérer le top-10 par market cap
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _row(label_core, label_pre, st):
    print(f"  {label_core:>9s} {label_pre:>8s} {st['cagr']*100:7.1f}% {st['sharpe']:7.2f} "
          f"{st['sortino']:8.2f} {st['max_drawdown']*100:7.1f}% {st.get('calmar', 0):7.2f} "
          f"{st['total_return']*100:8.1f}%")


def _sweep(title, preset, core, grid=(0.0, 0.25, 0.5, 0.75, 1.0)):
    from packages.backtest.index_core import _stats, blend_equity
    if not core or len(core) < 60:
        print(f"{title} : indisponible.\n"); return
    print(f"{title}")
    print(f"  {'Cœur':>9s} {'Preset':>8s} {'CAGR':>8s} {'Sharpe':>7s} "
          f"{'Sortino':>8s} {'maxDD':>8s} {'Calmar':>7s} {'Rdt tot.':>9s}")
    best = None
    for c in grid:
        eq, _ = blend_equity(preset, core, c)
        if not eq:
            continue
        st = _stats(eq)
        if not st.get("available"):
            continue
        _row(f"{c*100:.0f}%", f"{(1-c)*100:.0f}%", st)
        if c > 0 and (best is None or st["sharpe"] > best[1]["sharpe"]):
            best = (c, st)
    if best:
        print(f"  → meilleur Sharpe : {best[0]*100:.0f}% cœur (Sharpe {best[1]['sharpe']})\n")
    else:
        print()


def main() -> None:
    print("Construction du snapshot (preset de production réel)… ~30-60 s\n")
    from apps.api.snapshot import build_snapshot
    snap = build_snapshot()
    cur = snap.get("index_core_curves", {})
    ic = snap["dashboard"].get("index_core", {})
    preset, qqq, mc = cur.get("preset", []), cur.get("qqq", []), cur.get("megacap", [])
    if not preset:
        print("Preset indisponible."); return

    _sweep("CŒUR QQQ (Nasdaq 100, indice réel) + satellite preset", preset, qqq)
    wlabel = ic.get("mc_weighting", "—")
    note = "pondéré MARKET CAP réelle" if wlabel == "market_cap" else "proxy dollar-volume (lance ingest-mktcap)"
    _sweep(f"CŒUR TOP-10 MÉGA-CAPS ({note}) + satellite preset", preset, mc)

    # blend configuré en production (défaut 15% QQQ + 10% top-10 + 75% preset)
    if ic.get("enabled"):
        bs, base = ic.get("blended_stats", {}), ic.get("base_stats", {})
        comps = " + ".join(f"{int(round(c['pct']*100))}% {c['kind'].upper()}" for c in ic.get("components", []))
        print(f"✅ BLEND DE PRODUCTION : {comps} + {int(round((1-ic['core_pct'])*100))}% preset")
        if bs.get("available"):
            print(f"   Mélange  : CAGR {bs.get('cagr',0)*100:.1f}% · Sharpe {bs.get('sharpe')} · "
                  f"maxDD {bs.get('max_drawdown',0)*100:.1f}%")
        if base.get("available"):
            print(f"   Preset pur : CAGR {base.get('cagr',0)*100:.1f}% · Sharpe {base.get('sharpe')} · "
                  f"maxDD {base.get('max_drawdown',0)*100:.1f}%")
        if ic.get("core_holdings"):
            print(f"   Panier top-10 ({wlabel}) : {', '.join(ic['core_holdings'])}")
        print("   → actif dans le dashboard + l'allocation de production.")
    print("\n  ⚠️ Rééq. quotidien (turnover indicatif), sans frais de mélange. Le top-10 (proxy/cap) "
          "n'est pas corrigé du biais du survivant → indicatif.")
    print("  Changer le blend :  export QUANT_CORE_SPEC=\"qqq:0.15,megacap:0.10\"  (le reste = preset)")


if __name__ == "__main__":
    main()
