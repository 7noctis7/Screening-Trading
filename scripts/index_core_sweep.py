"""Sweep « cœur(s) indiciel(s) + satellite preset » sur ta VRAIE data.

SOURCE DE VÉRITÉ UNIQUE : on construit le snapshot UNE fois (preset de production réel + courbes
QQQ et top-10 méga-caps), puis on balaie instantanément tous les ratios localement. Le script et
le site partagent donc exactement la même mesure.

  export QUANT_PRICE_DB=/chemin/YAHOO.db
  python scripts/index_core_sweep.py                 # sweeps QQQ et top-10 + blend configuré
  python scripts/ingest_market_cap.py                # (avant) pour pondérer le top-10 par market cap
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _row(label_core, label_pre, st, sup=None):
    sup = sup or {}
    def _p(x):
        return "   —" if x is None else f"{x*100:3.0f}%"
    print(f"  {label_core:>9s} {label_pre:>8s} {st['cagr']*100:7.1f}% {st['sharpe']:7.2f} "
          f"{st['sortino']:8.2f} {st['max_drawdown']*100:7.1f}% "
          f"{_p(sup.get('psr')):>5s} {_p(sup.get('dsr')):>5s} "
          f"{sup.get('alpha_annual', 0)*100:7.1f}% {sup.get('t_alpha', 0):6.2f}")


def _capm(eq, ref) -> dict:
    """Alpha CAPM (rf = 0) de la variante contre le CŒUR, avec le t de l'alpha.

    Le t est ce qui manque partout : un alpha annualisé de 1,1 % ne veut rien dire tant
    qu'on ignore s'il est distinguable de zéro. Pour l'ordonnée à l'origine d'une
    régression, l'erreur-type vaut s_resid · sqrt(1/m + m_ref²/((m-1)·var_ref)) ;
    sur des rendements quotidiens le second terme est négligeable mais on le garde,
    parce qu'il ne coûte rien et qu'un raccourci non écrit se transmet.

    À 100 % de cœur, la variante EST la référence : alpha et t doivent valoir zéro.
    C'est le contrôle intégré de cette fonction.
    """
    a, b = _rendements(eq), _rendements(ref)
    m = min(len(a), len(b))
    if m < 30:
        return {}
    a, b = a[-m:], b[-m:]
    ma, mb = sum(a) / m, sum(b) / m
    var_b = sum((x - mb) ** 2 for x in b) / (m - 1)
    if var_b <= 0:
        return {}
    beta = sum((a[i] - ma) * (b[i] - mb) for i in range(m)) / (m - 1) / var_b
    alpha_j = ma - beta * mb
    resid = [a[i] - alpha_j - beta * b[i] for i in range(m)]
    s2 = sum(r * r for r in resid) / max(m - 2, 1)
    se = math.sqrt(s2 * (1.0 / m + mb * mb / ((m - 1) * var_b)))
    return {"alpha_annual": alpha_j * 252, "beta": beta,
            "t_alpha": (alpha_j / se) if se > 0 else 0.0}


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


def _essais(minimum: int = 20) -> int:
    """Essais RÉELS du registre de recherche + les cinq parts de cœur de ce sweep."""
    try:
        from packages.research.ledger import deflation_params
        deja, _ = deflation_params(min_trials=minimum)
    except Exception:  # noqa: BLE001
        deja = minimum
    return int(deja) + 5


def _sweep(title, preset, core, grid=(0.0, 0.25, 0.5, 0.75, 1.0), reference=0.5):
    from packages.backtest.index_core import _stats, blend_equity
    from packages.portfolio.psr import psr_dsr_depuis_rendements
    courbes: dict[float, list] = {}
    if not core or len(core) < 60:
        print(f"{title} : indisponible.\n"); return
    print(f"{title}")
    print(f"  {'Cœur':>9s} {'Preset':>8s} {'CAGR':>8s} {'Sharpe':>7s} "
          f"{'Sortino':>8s} {'maxDD':>8s} {'PSR':>5s} {'DSR':>5s} "
          f"{'alpha':>8s} {'t(α)':>6s}")
    best = None
    for c in grid:
        eq, _ = blend_equity(preset, core, c)
        if not eq:
            continue
        st = _stats(eq)
        if not st.get("available"):
            continue
        sup = dict(_capm(eq, core))
        _d = psr_dsr_depuis_rendements(_rendements(eq), n_trials=_essais())
        if _d.get("available"):
            sup["psr"], sup["dsr"] = _d["psr"], _d["dsr"]
        _row(f"{c*100:.0f}%", f"{(1-c)*100:.0f}%", st, sup)
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
