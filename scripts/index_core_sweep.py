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


def _rendements(eq):
    """Rendements quotidiens d'une courbe d'equity."""
    return [eq[i] / eq[i - 1] - 1.0 for i in range(1, len(eq)) if eq[i - 1] > 0]


def _verdict(courbes: dict, best, reference: float) -> None:
    """Le meilleur Sharpe de cinq essais est-il DISCERNABLE de la part actuelle ?

    Sans cette étape, le sweep est une machine à surapprendre : cinq ratios essayés, on
    garde le plus flatteur, et on lit du bruit comme un résultat. Le maximum de n
    tirages bruités croît en racine de 2·ln(n) : sur cinq essais on gagne « gratuitement »
    un demi-écart-type environ.

    La comparaison est APPARIÉE (mêmes dates, forte corrélation entre deux mélanges du
    même satellite). C'est exactement le cas que traite la correction de Jobson-Korkie /
    Memmel, et qui rend le test bien plus sensible qu'une comparaison indépendante.
    """
    from packages.research.sharpe_diff import comparer, seuil_detectable
    if reference not in courbes or best is None:
        return
    base = _rendements(courbes[reference])
    if len(base) < 60:
        return
    seuil = seuil_detectable(len(base), sharpe=1.0, rho=0.95, periodes_par_an=252.0)
    print(f"\n  Référence = part actuelle {reference*100:.0f}% · "
          f"plus petit écart de Sharpe détectable à 5 % : ±{seuil:.2f}")
    discernables = []
    for c, eq in sorted(courbes.items()):
        if c == reference:
            continue
        d = comparer(base, _rendements(eq), periodes_par_an=252.0)
        if not d.get("disponible"):
            continue
        marque = "  ← DISCERNABLE" if d["verdict"] != "indiscernable" else ""
        if marque:
            discernables.append((c, d))
        ic = f"{d['ic95'][0]:+.2f} à {d['ic95'][1]:+.2f}"
        print(f"    {c*100:>3.0f}% cœur : ΔSharpe {d['delta']:+.2f} "
              f"(IC95 {ic}, p={d['p']:.3f}){marque}")
    if not discernables:
        print("  → AUCUN ratio n'est distinguable de la part actuelle. Le « meilleur "
              f"Sharpe » affiché ({best[0]*100:.0f}%) est du bruit de sélection : "
              "ne pas bouger sur cette base.")
    else:
        noms = ", ".join(f"{c*100:.0f}%" for c, _ in discernables)
        print(f"  → discernable(s) : {noms}. À confirmer hors échantillon avant "
              "de bouger (5 ratios essayés — le comptage voyage avec le chiffre).")


def _sweep(title, preset, core, grid=(0.0, 0.25, 0.5, 0.75, 1.0), reference=0.5):
    from packages.backtest.index_core import _stats, blend_equity
    courbes: dict[float, list] = {}
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
        courbes[c] = eq
        if c > 0 and (best is None or st["sharpe"] > best[1]["sharpe"]):
            best = (c, st)
    _verdict(courbes, best, reference)
    print()


def main() -> None:
    print("Construction du snapshot (preset de production réel)… ~30-60 s\n")
    from apps.api.snapshot import build_snapshot
    snap = build_snapshot()
    cur = snap.get("index_core_curves", {})
    ic = snap["dashboard"].get("index_core", {})
    preset, qqq, mc = cur.get("preset", []), cur.get("qqq", []), cur.get("megacap", [])
    sm = cur.get("sector_mom", [])
    if not preset:
        print("Preset indisponible."); return

    _sweep("CŒUR QQQ (Nasdaq 100, indice réel) + satellite preset", preset, qqq)
    wlabel = ic.get("mc_weighting", "—")
    note = "pondéré MARKET CAP réelle" if wlabel == "market_cap" else "proxy dollar-volume (lance ingest-mktcap)"
    _sweep(f"CŒUR TOP-10 MÉGA-CAPS ({note}) + satellite preset", preset, mc)
    _sweep("CŒUR MOMENTUM SECTORIEL (top-2 secteurs 6 mois, mensuel, filtre MM50) + satellite preset", preset, sm)

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
