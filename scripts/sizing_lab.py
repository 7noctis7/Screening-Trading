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
    return data, acmap, mode, len(reels), debut, fin


def _vix(data, debut, fin, seed: int = 7):
    """Le VIX de PRODUCTION, et non son absence.

    `fast_swing` module l'exposition brute autorisée par `vix_exposure` : ×1,0 sous 20,
    ×0,7 entre 20 et 30, ×0,4 au-delà. Sans série VIX le multiplicateur reste à 1,0 —
    donc au MAXIMUM en permanence, y compris dans les krachs. Or c'est `allowed_gross`
    qui détermine `room`, et `room` est exactement le mécanisme qu'on teste : un banc
    sans VIX sous-représente les troncatures qu'il est censé mesurer.
    """
    from apps.api.snapshot import _index_closes, _vix_series
    n = max(len(b) for b in data.values())
    reel, est_reel = _index_closes(["^VIX", "VIX"], debut, fin, [])
    if est_reel and len(reel) >= 50:
        return reel[-n:] if len(reel) >= n else [reel[0]] * (n - len(reel)) + reel
    return _vix_series(n, seed)


def _expo_moyenne(trades, equity: list[float], jours: int) -> float:
    """Exposition brute moyenne, pondérée par le TEMPS de détention.

    Sans elle, on compare deux dimensionnements ET deux niveaux de levier à la fois :
    un net trois fois plus bas peut ne signifier qu'un portefeuille trois fois moins
    investi, ce qui ne dit rien de la qualité de la règle de taille.
    """
    if not equity or jours <= 0:
        return 0.0
    moy_eq = sum(equity) / len(equity)
    jour = 86400.0
    engage = sum(t.qty * t.entry_price
                 * max((t.exit_ts - t.entry_ts).total_seconds(), 0.0) / jour
                 for t in trades if t.exit_ts and t.entry_ts)
    return engage / (jours * moy_eq) if moy_eq > 0 else 0.0


def _run(data, acmap, risque: float, vix=None):
    from packages.backtest.fast_swing import fast_swing_backtest
    from packages.execution.costs import CostModel
    from packages.portfolio import fragilite as F

    _, journal, equity, _ = fast_swing_backtest(
        data, cash=10_000, costs=CostModel(), asset_classes=acmap,
        target_annual_vol=0.30, max_capital_frac=0.15, max_positions=20, max_pct=0.20,
        atr_stop=4.0, rr=6.0, vix=vix, close_at_end=False, daily_max_loss=0.06,
        trail_atr=5.0, next_open_fills=True, risque_par_trade=risque)
    trades = [t for t in journal.all() if t.pnl_net is not None]
    trades.sort(key=lambda t: t.exit_ts or t.entry_ts)
    pnls = [t.pnl_net for t in trades]
    rs = [t.r_multiple for t in trades]
    return {"equity": equity, "n": len(pnls), "net": sum(pnls),
            "expo": _expo_moyenne(trades, equity, len(equity)),
            **F.marge_de_payoff(pnls), **F.concentration(pnls),
            **F.significativite(pnls), **F.dependance(pnls),
            **F.comparer_dimensionnement(pnls, rs)}


def _rendements(equity: list[float]) -> list[float]:
    return [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))
            if equity[i - 1] > 0]


def _ligne(nom: str, r: dict, sharpe: float | None = None) -> str:
    return (f"{nom:>12} | {r['n']:>5} | {r.get('profit_factor_sans_top5', 0):>6.2f} "
            f"| {r.get('t_esperance', 0):>5.2f} | {r.get('t_effectif', 0):>5.2f} "
            f"| {r.get('n_effectif', 0):>5} | {r.get('expo', 0):>7.1%} "
            f"| {'—' if sharpe is None else f'{sharpe:>6.2f}'} | {r['net']:>10,.0f}")


def main() -> None:
    from packages.research.sharpe_diff import comparer
    risques = [float(a) for a in sys.argv[1:]] or RISQUES
    data, acmap, mode, n_reels, debut, fin = _donnees()
    print(f"\ndonnées : {len(data)} symboles · mode {mode} · {n_reels} à prix réels\n")
    if n_reels < 30:
        print("⚠️  AUCUNE base réelle branchée — ce banc ne décide de rien "
              "sur du synthétique.")
        return

    vix = _vix(data, debut, fin)
    base = _run(data, acmap, 0.0, vix)
    rb = _rendements(base["equity"])
    s_base = comparer(rb, rb, periodes_par_an=252.0).get("sharpe_base")
    print(f"{'dimension.':>12} | {'trades':>5} | {'PF-5':>6} | {'t':>5} | {'t eff':>5} "
          f"| {'n eff':>5} | {'expo':>7} | {'Sharpe':>6} | {'net $':>10}")
    print("-" * 92)
    print(_ligne("notionnel", base, s_base))

    for risque in risques:
        r = _run(data, acmap, risque, vix)
        # 252 : les rendements sont QUOTIDIENS. Le défaut de `comparer` est mensuel,
        # et l'oublier annualiserait le Sharpe par sqrt(12) au lieu de sqrt(252).
        d = comparer(rb, _rendements(r["equity"]), periodes_par_an=252.0)
        if not d.get("disponible"):
            print(_ligne(f"risque {risque:.1%}", r))
            print(f"{'':>12} | {d.get('raison')}")
            continue
        print(_ligne(f"risque {risque:.1%}", r, d["sharpe_variante"]))
        print(f"{'':>12} | ΔSharpe {d['delta']:+.3f} · IC95 {d['ic95']} "
              f"· p = {d['p']:.4f} · {d['verdict'].upper()}")

    print("\nPF-5 = profit factor privé des cinq meilleurs trades ; sous 1,00 le "
          "résultat tient à\ncinq lignes. `t eff` corrige la dépendance entre trades "
          "qui se chevauchent.\n\n`t` MONTE MÉCANIQUEMENT AVEC LE NOMBRE DE TRADES "
          "(il vaut espérance/écart-type × sqrt(n)) :\nentre deux variantes de "
          "cardinalités différentes, il n'est pas comparable. Le seul\narbitre à "
          "l'échelle près est le Sharpe, et `expo` dit si les deux jouent bien le\n"
          "même niveau d'investissement.\n")


if __name__ == "__main__":
    main()
