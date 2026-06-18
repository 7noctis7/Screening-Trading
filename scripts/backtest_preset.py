"""Backtest WALK-FORWARD du preset « best practice » + overlay volatilité gérée — sur TES données.

  export QUANT_PRICE_DB=/chemin/vers/YAHOO.db   # (sinon synthétique)
  python scripts/backtest_preset.py

Tout est calculé point-in-time par le pipeline (anti-fuite) :
  - PRESET = tilt qualité → risk-parity (ERC) → DD-target → earnings blackout → no-trade band,
    net de coûts par classe ; comparé au swing actuel et à l'équipondéré (même univers).
  - VOLATILITÉ GÉRÉE (Moreira-Muir) = overlay sur les rendements quotidiens de la stratégie
    (exposition ∝ vol-cible / vol réalisée récente). C'est là que le clustering de vol RÉEL paie.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _row(label: str, st: dict, *, cagr_key: str = "annualized") -> str:
    cagr = st.get(cagr_key, st.get("cagr", 0.0))
    return (f"  {label:30s} {cagr*100:7.1f}% {st.get('sharpe', 0):7.2f} "
            f"{st.get('max_drawdown', 0)*100:7.1f}% {st.get('total_return', 0)*100:8.1f}%")


def main() -> None:
    from apps.api.snapshot import build_snapshot
    print("Construction du snapshot (peut prendre 1-2 min sur la vraie base)…")
    s = build_snapshot()
    print(f"\nMode des données : {s['meta']['mode']} · univers {s['meta']['universe_size']}")
    if s["meta"].get("data_synthetic") and __import__("os").environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print("\n⛔ DONNÉES SYNTHÉTIQUES (factices) — backtest INUTILE et trompeur.")
        print("   Branche tes vraies données : export QUANT_PRICE_DB=\"$HOME/Desktop/YAHOO.db\"")
        print("   (ou QUANT_ALLOW_SYNTHETIC=1 pour forcer la démo, à tes risques).")
        return

    a = s["portfolio"]["analysis"]
    pb = (a.get("recommended_allocation") or {}).get("preset_backtest") or {}
    vm = (a.get("risk") or {}).get("vol_managed") or {}

    print("\n" + "=" * 74)
    print("PRESET « best practice » — backtest walk-forward (point-in-time, net de coûts)")
    print("=" * 74)
    if pb.get("available"):
        print(f"Univers qualité top {pb['top_k']} · pas {pb['step_days']} j · DD-cible "
              f"{pb['dd_target']*100:.0f}% · bande {pb['band']*100:.0f}% · turnover "
              f"{pb['turnover_annual']}×/an · exposition brute moy. {pb['avg_gross']*100:.0f}%\n")
        print(f"  {'Stratégie':30s} {'CAGR':>8s} {'Sharpe':>7s} {'maxDD':>8s} {'Rdt tot.':>9s}")
        if pb.get("preset"):    print(_row("Preset (best practice)", pb["preset"]))
        if pb.get("swing"):     print(_row("Swing (actuel)", pb["swing"]))
        if pb.get("benchmark"): print(_row("Équipondéré (même univers)", pb["benchmark"]))
    else:
        print("  Indisponible (échantillon insuffisant).")

    print("\n" + "=" * 74)
    print("VOLATILITÉ GÉRÉE (Moreira-Muir) — overlay sur les rendements quotidiens")
    print("=" * 74)
    if vm.get("available"):
        print(f"Vol-cible {vm['target_vol']*100:.0f}% · fenêtre {vm['window']} j · sans levier · "
              f"exposition moy. {vm['avg_exposure']*100:.0f}%\n")
        print(f"  {'Série':30s} {'CAGR':>8s} {'Sharpe':>7s} {'maxDD':>8s} {'Vol':>9s}")
        for lab, key in (("Brute", "raw"), ("Volatilité gérée", "managed")):
            st = vm.get(key, {})
            print(f"  {lab:30s} {st.get('cagr',0)*100:7.1f}% {st.get('sharpe',0):7.2f} "
                  f"{st.get('max_drawdown',0)*100:7.1f}% {st.get('vol',0)*100:8.1f}%")
        print(f"\n  → Gain Sharpe {vm['sharpe_gain']:+.2f} · Δ CAGR {vm['cagr_gain']*100:+.1f} pts · "
              f"DD {vm['dd_reduction']*100:+.1f} pts")
        print("  (Le bénéfice vient du CLUSTERING de vol des marchés réels ; quasi nul sur synthétique.)")
    else:
        print("  Indisponible.")

    print("\nLecture : viser le meilleur SHARPE et le plus faible DRAWDOWN, pas le CAGR brut. "
          "Sans edge directionnel prouvé (DSR≈0), la gestion du risque est le levier fiable.")


if __name__ == "__main__":
    main()
