"""Démo walk-forward + deflated Sharpe (offline, reproductible).

  python scripts/demo_walkforward.py

Sélection de params in-sample → évaluation OUT-OF-SAMPLE → métriques OOS + DSR.
Le DSR corrige le multiple testing : un Sharpe OOS modeste après N essais n'est
PAS significatif. Sur données synthétiques quasi-aléatoires, DSR ≈ 0 (attendu).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.backtest import WalkForwardRunner  # noqa: E402
from packages.data import data_providers  # noqa: E402
from packages.execution import CostModel, SimBroker  # noqa: E402
from packages.portfolio.sizing import sizers  # noqa: E402
from packages.risk import RiskEngine, risk_rules  # noqa: E402
from packages.strategies import strategies  # noqa: E402


def main() -> int:
    start = datetime(2017, 1, 1, tzinfo=timezone.utc)
    data = {s: data_providers.create("synthetic", seed=7, drift=0.08).fetch_ohlcv(
        s, "1d", start, start + timedelta(days=365 * 7)) for s in ("A", "B", "C", "D")}
    runner = WalkForwardRunner(
        strategy_factory=lambda **p: strategies.create("ma_crossover", **p),
        sizer=sizers.create("vol_target", max_capital_frac=0.10),
        risk_factory=lambda: RiskEngine(
            [risk_rules.create("max_exposure_per_asset", max_pct=0.10)]),
        broker_factory=lambda: SimBroker(cash=100_000, costs=CostModel()),
        train=504, test=126, warmup=252)
    grid = [{"fast": 10, "slow": 30}, {"fast": 20, "slow": 50},
            {"fast": 50, "slow": 100}, {"fast": 30, "slow": 80}]
    res = runner.run(data, grid)
    m = res.oos_metrics
    print("\n" + "=" * 56)
    print(" WALK-FORWARD — validation out-of-sample")
    print("=" * 56)
    print(f" Fenêtres            : {len(res.chosen_params)}")
    print(f" Essais (grille×fen.): {res.n_trials}")
    print(f" Rendement OOS       : {m['total_return']:+.1%}")
    print(f" Sharpe OOS          : {m['sharpe']:.2f}")
    print(f" Max drawdown OOS    : {m['max_drawdown']:.1%}")
    print(f" PSR (vs 0)          : {res.psr:.2f}")
    print(f" DEFLATED Sharpe     : {res.deflated_sharpe:.2f}")
    verdict = "significatif" if res.deflated_sharpe > 0.95 else "NON significatif (multiple testing)"
    print(f" Verdict             : {verdict}")
    print("=" * 56 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
