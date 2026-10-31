#!/usr/bin/env python3
"""Banc de VITESSE des moteurs de backtest — mesure le temps, jamais un résultat.

  python scripts/bench_moteur.py                      # 10 et 50 actifs × 10 ans, 3 passages
  python scripts/bench_moteur.py --actifs 100 --ans 5 --passages 5

Données SYNTHÉTIQUES seedées (comme `demo_backtest.py`) : elles servent de charge de
travail reproductible pour le chronomètre. Aucun rendement, Sharpe ou seuil n'est lu ici —
le mandat données-réelles s'applique à toute mesure de performance financière.

Deux moteurs :
- `event-driven` : la chaîne complète (régime → stratégie → risque → sizing → broker →
  journal), exécution à l'ouverture de t+1 — celle qui sert à juger une règle ;
- `vectorisé` : `fast_swing_backtest`, le balayage rapide des grilles.
Résultat : médiane des passages, en secondes et en barres·actif par seconde.
"""
from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.backtest import BacktestEngine  # noqa: E402
from packages.backtest.fast_swing import fast_swing_backtest  # noqa: E402
from packages.data import data_providers  # noqa: E402
from packages.execution import CostModel, SimBroker  # noqa: E402
from packages.portfolio.sizing import sizers  # noqa: E402
from packages.risk import RiskEngine, risk_rules  # noqa: E402
from packages.strategies import strategies  # noqa: E402


def charge(n_actifs: int, ans: int) -> dict[str, list]:
    """{symbole: [Bar]} quotidiens, seedés : la même charge à chaque appel."""
    fournisseur = data_providers.create("synthetic", seed=7, annual_vol=0.28, drift=0.08)
    debut = datetime(2015, 1, 1, tzinfo=timezone.utc)
    fin = debut + timedelta(days=365 * ans)
    return {f"S{i:03d}": fournisseur.fetch_ohlcv(f"S{i:03d}", "1d", debut, fin)
            for i in range(n_actifs)}


def _event_driven(data: dict[str, list]) -> None:
    risque = RiskEngine([risk_rules.create("max_positions", max_positions=20),
                         risk_rules.create("max_exposure_per_asset", max_pct=0.10)],
                        max_daily_drawdown_pct=0.05)
    moteur = BacktestEngine(
        strategies.create("ma_crossover", fast=20, slow=50, atr_stop=2.0, rr=2.5),
        sizers.create("vol_target", target_annual_vol=0.15, max_capital_frac=0.10),
        risque, SimBroker(cash=100_000.0, costs=CostModel(fee_bps=5, slippage_bps=2)))
    moteur.run(data)


def _vectorise(data: dict[str, list]) -> None:
    fast_swing_backtest(data)


MOTEURS = {"event-driven": _event_driven, "vectorisé": _vectorise}


def chronometrer(fn, data: dict[str, list], passages: int) -> float:
    """Médiane des temps de `passages` exécutions (secondes, horloge monotone)."""
    temps = []
    for _ in range(passages):
        t0 = time.perf_counter()
        fn(data)
        temps.append(time.perf_counter() - t0)
    return statistics.median(temps)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--actifs", type=int, nargs="*", default=[10, 50])
    ap.add_argument("--ans", type=int, default=10)
    ap.add_argument("--passages", type=int, default=3)
    a = ap.parse_args(argv)
    print(f"Python {platform.python_version()} · {platform.machine()} · "
          f"{platform.processor() or platform.platform()}")
    print(f"{'moteur':14} {'actifs':>6} {'barres':>7} {'médiane':>9} {'barres·actif/s':>15}")
    for n in a.actifs:
        data = charge(n, a.ans)
        barres = sum(len(v) for v in data.values())
        for nom, fn in MOTEURS.items():
            s = chronometrer(fn, data, a.passages)
            print(f"{nom:14} {n:>6} {barres // n:>7} {s:>8.2f}s {barres / s:>15,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
