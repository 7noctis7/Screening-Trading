from datetime import datetime, timedelta, timezone
from packages.backtest import BacktestEngine
from packages.data import data_providers
from packages.execution import CostModel, SimBroker
from packages.risk import RiskEngine, risk_rules
from packages.portfolio.sizing import sizers
from packages.strategies import strategies


def _run():
    prov = data_providers.create("synthetic", seed=3)
    start = datetime(2021, 1, 1, tzinfo=timezone.utc)
    data = {s: prov.fetch_ohlcv(s, "1d", start, start + timedelta(days=600))
            for s in ("A", "B")}
    strat = strategies.create("ma_crossover", fast=10, slow=30)
    sizer = sizers.create("vol_target", max_capital_frac=0.10)
    risk = RiskEngine([risk_rules.create("max_exposure_per_asset", max_pct=0.10)])
    broker = SimBroker(cash=100_000, costs=CostModel())
    return BacktestEngine(strat, sizer, risk, broker).run(data), broker


def test_engine_runs_and_is_consistent():
    result, broker = _run()
    assert len(result.equity_curve) == len(result.timestamps) > 0
    assert result.equity_curve[0] == 100_000  # capital initial intact au départ
    # equity finale = ce que dit le broker
    assert abs(result.equity_curve[-1] - broker.equity()) < 1.0


def test_r_multiple_on_stop_is_minus_one():
    result, _ = _run()
    stops = [t for t in result.journal.all() if t.exit_reason == "stop_hit"]
    for t in stops:
        assert t.r_multiple is not None and abs(t.r_multiple + 1.0) < 0.05
