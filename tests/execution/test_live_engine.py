from datetime import datetime, timedelta, timezone
from packages.data import data_providers
from packages.execution import SimBroker, CostModel, LiveTradingEngine
from packages.risk import RiskEngine, risk_rules
from packages.portfolio.sizing import sizers
from packages.strategies import strategies


def _engine(broker):
    return LiveTradingEngine(
        strategy=strategies.create("ma_crossover", fast=10, slow=30),
        sizer=sizers.create("vol_target", max_capital_frac=0.10),
        risk_engine=RiskEngine([risk_rules.create("max_exposure_per_asset", max_pct=0.10)]),
        broker=broker)


def test_live_step_runs_and_reconciles():
    start = datetime(2021, 1, 1, tzinfo=timezone.utc)
    bars = data_providers.create("synthetic", seed=7, drift=0.08).fetch_ohlcv(
        "AAPL", "1d", start, start + timedelta(days=300))
    eng = _engine(SimBroker(cash=100_000, costs=CostModel()))
    for i in range(40, len(bars)):
        eng.step({"AAPL": bars[: i + 1]})
    assert eng.reconcile().ok                 # broker == interne (parité)
    assert isinstance(eng.kill_switch, bool)


def test_kill_switch_blocks_entries():
    # kill-switch armé → le chemin d'ouverture refuse l'ordre (veto), zéro position
    from datetime import datetime as _dt
    from packages.core.models import Bar, Signal, SignalDirection
    broker = SimBroker(cash=100_000, costs=CostModel())
    risk = RiskEngine([], max_daily_drawdown_pct=0.05)
    risk.new_day(100_000)
    risk.mark_equity(50_000)                 # -50 % → kill-switch armé
    eng = LiveTradingEngine(
        strategy=strategies.create("ma_crossover"), risk_engine=risk, broker=broker,
        sizer=sizers.create("vol_target", max_capital_frac=0.10))
    assert eng.kill_switch is True
    ts = _dt(2021, 1, 4, tzinfo=timezone.utc)
    bar = Bar("AAPL", "1d", ts, 100, 101, 99, 100, 1000)
    broker.mark("AAPL", 100)
    sig = Signal("AAPL", SignalDirection.LONG, "s", ts, stop=98, target=106,
                 features={"atr": 2.0})
    eng._try_open("AAPL", sig, bar, None)
    assert broker.positions() == [] and "AAPL" not in eng._open
