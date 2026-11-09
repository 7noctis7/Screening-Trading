#!/usr/bin/env python3
"""Banc de VITESSE des moteurs de backtest, sur les VRAIES barres de la base de prix.

  python scripts/bench_moteur.py                      # 10 et 50 actifs × 10 ans, 3 passages
  python scripts/bench_moteur.py --actifs 5 --ans 4 --passages 1
  python scripts/bench_moteur.py --db ~/Desktop/market.db

Mandat données-réelles : la charge vient de `data/market.db` (ou `--db`, format LONG), les
N premiers symboles par ordre alphabétique qui couvrent la période — reproductible sur une
même base. Sans base suffisante : UNCALIBRATED, rien n'est inventé. Seul le TEMPS est lu ;
aucun rendement, Sharpe ou seuil.

Deux moteurs :
- `event-driven` : la chaîne complète (stratégie → risque → sizing → broker → journal),
  exécution à l'ouverture de t+1 — celle qui sert à juger une règle ;
- `vectorisé` : `fast_swing_backtest`, le balayage rapide des grilles.
"""
from __future__ import annotations

import argparse
import platform
import sqlite3
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.backtest import BacktestEngine  # noqa: E402
from packages.backtest.fast_swing import fast_swing_backtest  # noqa: E402
from packages.data.engine import _resolve_db  # noqa: E402
from packages.data.providers.db_provider import DBPriceProvider  # noqa: E402
from packages.execution import CostModel, SimBroker  # noqa: E402
from packages.portfolio.sizing import sizers  # noqa: E402
from packages.risk import RiskEngine, risk_rules  # noqa: E402
from packages.strategies import strategies  # noqa: E402

BARRES_PAR_AN = 240   # plancher prudent de séances par an pour retenir un symbole


def charge(base: Path, n_actifs: int, ans: int) -> dict[str, list] | None:
    """{symbole: [Bar]} réels sur les `ans` dernières années ; None si la base ne suffit pas."""
    if not base.exists():
        return None
    with sqlite3.connect(f"file:{base}?mode=ro", uri=True) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='prices'").fetchone():
            return None
        fin = conn.execute("SELECT MAX(date) FROM prices").fetchone()[0]
        debut = (datetime.fromisoformat(fin) - timedelta(days=365 * ans)).date().isoformat()
        symboles = [r[0] for r in conn.execute(
            "SELECT symbol FROM prices WHERE date >= ? AND close > 0 GROUP BY symbol "
            "HAVING COUNT(*) >= ? ORDER BY symbol LIMIT ?", (debut, BARRES_PAR_AN * ans, n_actifs))]
    if len(symboles) < n_actifs:
        return None
    fournisseur = DBPriceProvider(base)
    t0 = datetime.fromisoformat(debut).replace(tzinfo=timezone.utc)
    t1 = datetime.fromisoformat(fin).replace(tzinfo=timezone.utc) + timedelta(days=1)
    return {s: fournisseur.fetch_ohlcv(s, "1d", t0, t1) for s in symboles}


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
    ap.add_argument("--db", default="market", help="base de prix au format LONG")
    a = ap.parse_args(argv)
    base = _resolve_db(a.db)
    print(f"Python {platform.python_version()} · {platform.machine()} · base {base}")
    print(f"{'moteur':14} {'actifs':>6} {'barres':>7} {'médiane':>9} {'barres·actif/s':>15}")
    for n in a.actifs:
        data = charge(base, n, a.ans)
        if data is None:
            print(f"UNCALIBRATED : {base.name} n'a pas {n} symboles couvrant {a.ans} ans "
                  "(ou n'existe pas) — rien n'est mesuré.")
            continue
        barres = sum(len(v) for v in data.values())
        for nom, fn in MOTEURS.items():
            s = chronometrer(fn, data, a.passages)
            print(f"{nom:14} {n:>6} {barres // n:>7} {s:>8.2f}s {barres / s:>15,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
