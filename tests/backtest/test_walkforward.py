from datetime import datetime, timedelta, timezone
from packages.data import data_providers
from packages.execution import CostModel, SimBroker
from packages.risk import RiskEngine, risk_rules
from packages.portfolio.sizing import sizers
from packages.strategies import strategies
from packages.backtest import WalkForwardRunner, make_windows


def test_make_windows_non_overlapping_test():
    w = make_windows(1000, train=500, test=100)
    assert w[0] == (0, 500, 500, 600)
    assert len(w) == 5                      # starts 0,100,200,300,400
    # tests contigus, non chevauchants
    for i in range(1, len(w)):
        assert w[i][2] == w[i - 1][3]


def test_runner_produces_oos_and_dsr():
    start = datetime(2018, 1, 1, tzinfo=timezone.utc)
    data = {s: data_providers.create("synthetic", seed=7).fetch_ohlcv(
        s, "1d", start, start + timedelta(days=365 * 5)) for s in ("A", "B")}
    runner = WalkForwardRunner(
        strategy_factory=lambda **p: strategies.create("ma_crossover", **p),
        sizer=sizers.create("vol_target", max_capital_frac=0.10),
        risk_factory=lambda: RiskEngine([risk_rules.create("max_exposure_per_asset", max_pct=0.10)]),
        broker_factory=lambda: SimBroker(cash=100_000, costs=CostModel()),
        train=504, test=126, warmup=252)
    grid = [{"fast": 10, "slow": 30}, {"fast": 20, "slow": 50}]
    res = runner.run(data, grid)
    assert len(res.chosen_params) >= 1
    assert res.n_trials == len(res.chosen_params) * len(grid)  # essais comptés
    assert 0.0 <= res.deflated_sharpe <= 1.0
    assert 0.0 <= res.psr <= 1.0
    assert "sharpe" in res.oos_metrics
