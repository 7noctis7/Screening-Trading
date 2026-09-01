#!/usr/bin/env python3
"""Notionnel contre risque constant, sur les données RÉELLES et à signaux identiques.

POURQUOI CE BANC EXISTE. La comparaison en R (t = 0,94 en dollars contre 2,00 en R sur
les 477 trades) est une CONTREFACTUELLE : elle dit ce qu'on aurait obtenu à risque égal
en supposant les mêmes entrées et les mêmes sorties. Or redimensionner change le capital
disponible, donc les trades qu'on peut prendre. L'indication est forte ; elle n'est pas
la preuve. Seul un re-run complet tranche, et c'est ce que fait ce script.

Il rejoue le backtest de production, à paramètres identiques, en ne changeant QUE le
dimensionnement, puis compare les deux courbes par le test de Jobson-Korkie corrigé
Memmel — apparié, car les deux séries partagent le même marché et le même calendrier.

    python scripts/sizing_lab.py                 # 0 (actuel) vs 0.5 %, 1 %, 2 %
    python scripts/sizing_lab.py 0.01 0.015      # fractions de risque au choix
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RISQUES = [0.005, 0.01, 0.02]


def _donnees():
    """Le MÊME univers et la même fenêtre que la production — sinon on compare deux
    expériences différentes et l'écart mesuré ne veut plus rien dire."""
    from apps.api.snapshot import (
        _HISTORY_DAYS,
        _load_prices,
        _sector_of,
        _seed_universe,
    )
    instruments = _seed_universe()
    acmap = {m["symbol"]: m["asset_class"] for m in instruments}
    secteur = {m["symbol"]: _sector_of(m) for m in instruments}
    fin = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    debut = fin - timedelta(days=_HISTORY_DAYS)
    data, mode, reels = _load_prices(instruments, secteur, debut, fin, 7)
    if len(reels) >= 30:            # zéro prix synthétique dans un banc de décision
        data = {s: b for s, b in data.items() if s in reels}
    return data, acmap, mode, len(reels)


def _run(data, acmap, risque: float):
    from packages.backtest.fast_swing import fast_swing_backtest
    from packages.execution.costs import CostModel
    from packages.portfolio import fragilite as F

    _, journal, equity, _ = fast_swing_backtest(
        data, cash=10_000, costs=CostModel(), asset_classes=acmap,
        target_annual_vol=0.30, max_capital_frac=0.15, max_positions=20, max_pct=0.20,
        atr_stop=4.0, rr=6.0, close_at_end=False, daily_max_loss=0.06,
        trail_atr=5.0, next_open_fills=True, risque_par_trade=risque)
    trades = [t for t in journal.all() if t.pnl_net is not None]
    trades.sort(key=lambda t: t.exit_ts or t.entry_ts)
    pnls = [t.pnl_net for t in trades]
    rs = [t.r_multiple for t in trades]
    return {"equity": equity, "n": len(pnls), "net": sum(pnls),
            **F.marge_de_payoff(pnls), **F.concentration(pnls),
            **F.significativite(pnls), **F.dependance(pnls),
            **F.comparer_dimensionnement(pnls, rs)}


def _rendements(equity: list[float]) -> list[float]:
    return [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))
            if equity[i - 1] > 0]


def _ligne(nom: str, r: dict) -> str:
    return (f"{nom:>12} | {r['n']:>5} | {r.get('profit_factor_sans_top5', 0):>6.2f} "
            f"| {r.get('t_esperance', 0):>6.2f} | {r.get('t_effectif', 0):>6.2f} "
            f"| {r.get('n_effectif', 0):>5} | {r['net']:>12,.0f}")


def main() -> None:
    from packages.research.sharpe_diff import comparer
    risques = [float(a) for a in sys.argv[1:]] or RISQUES
    data, acmap, mode, n_reels = _donnees()
    print(f"\ndonnées : {len(data)} symboles · mode {mode} · {n_reels} à prix réels\n")
    if n_reels < 30:
        print("⚠️  AUCUNE base réelle branchée — ce banc ne décide de rien "
              "sur du synthétique.")
        return

    base = _run(data, acmap, 0.0)
    print(f"{'dimension.':>12} | {'trades':>5} | {'PF-5':>6} | {'t':>6} | {'t eff':>6} "
          f"| {'n eff':>5} | {'net $':>12}")
    print("-" * 74)
    print(_ligne("notionnel", base))

    rb = _rendements(base["equity"])
    for risque in risques:
        r = _run(data, acmap, risque)
        print(_ligne(f"risque {risque:.1%}", r))
        # 252 : les rendements sont QUOTIDIENS. Le défaut de `comparer` est mensuel,
        # et l'oublier annualiserait le Sharpe par sqrt(12) au lieu de sqrt(252).
        d = comparer(rb, _rendements(r["equity"]), periodes_par_an=252.0)
        if not d.get("disponible"):
            print(f"{'':>12} | {d.get('raison')}")
            continue
        print(f"{'':>12} | ΔSharpe {d['delta']:+.3f} · IC95 {d['ic95']} "
              f"· p = {d['p']:.4f} · {d['verdict'].upper()}")

    print("\nPF-5 = profit factor privé des cinq meilleurs trades. Sous 1,00, "
          "le résultat tient\nà cinq lignes. `t eff` corrige la dépendance entre "
          "trades qui se chevauchent.\n")


if __name__ == "__main__":
    main()
