"""Démo boucle paper (offline, SimBroker) — parité avec le backtest.

  python scripts/demo_paper_loop.py

Le LiveTradingEngine réutilise les MÊMES Strategy/Sizer/RiskEngine/Broker/Journal
que le backtest, mais réagit barre par barre (streaming). Réconciliation broker↔interne
à la fin. Pour le vrai paper Alpaca : remplacer SimBroker par AlpacaBroker (AlpacaBroker(paper=True)).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.data import data_providers  # noqa: E402
from packages.execution import CostModel, LiveTradingEngine, SimBroker  # noqa: E402
from packages.portfolio.sizing import sizers  # noqa: E402
from packages.risk import RiskEngine, risk_rules  # noqa: E402
from packages.storage import SqliteTradeJournal  # noqa: E402
from packages.strategies import strategies  # noqa: E402


def main() -> int:
    start = datetime(2021, 1, 1, tzinfo=timezone.utc)
    syms = ["AAPL", "MSFT", "NVDA"]
    data = {s: data_providers.create("synthetic", seed=7, drift=0.08).fetch_ohlcv(
        s, "1d", start, start + timedelta(days=500)) for s in syms}
    broker = SimBroker(cash=100_000, costs=CostModel())
    eng = LiveTradingEngine(
        strategy=strategies.create("ma_crossover", fast=20, slow=50),
        sizer=sizers.create("vol_target", max_capital_frac=0.10),
        risk_engine=RiskEngine([risk_rules.create("max_positions", max_positions=10),
                                risk_rules.create("max_exposure_per_asset", max_pct=0.10)],
                               max_daily_drawdown_pct=0.05),
        broker=broker, journal=SqliteTradeJournal(":memory:"))  # démo synthétique : pas de journal réel

    n = max(len(b) for b in data.values())
    for i in range(60, n):                       # streaming : un pas par barre
        eng.step({s: data[s][: i + 1] for s in syms})

    rec = eng.reconcile()
    print("\n" + "=" * 56)
    print(" BOUCLE PAPER (SimBroker) — parité backtest↔live")
    print("=" * 56)
    print(f" Equity finale     : {broker.equity():,.0f}")
    print(f" Positions ouvertes: {[p.instrument for p in broker.positions()]}")
    print(f" Trades clôturés   : {len(eng.journal.all())}")
    print(f" Kill-switch armé  : {eng.kill_switch}")
    print(f" Réconciliation OK : {rec.ok}")
    print("=" * 56 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
