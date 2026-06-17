from datetime import datetime, timezone

from packages.backtest.fast_swing import fast_swing_backtest, vix_exposure
from packages.core.models import Bar


def _series(sym, prices):
    t0 = datetime(2021, 1, 1, tzinfo=timezone.utc)
    from datetime import timedelta
    return [Bar(sym, "1d", t0 + timedelta(days=i), p, p * 1.01, p * 0.99, p, 1e6)
            for i, p in enumerate(prices)]


def test_vix_exposure_playbook():
    # sans levier : ≤ 100% (calme=1.0), réduit en stress
    assert vix_exposure(10) == 1.0 and vix_exposure(16) == 1.0
    assert vix_exposure(25) == 0.7 and vix_exposure(40) == 0.4


def test_backtest_runs_with_risk_controls():
    from datetime import timedelta
    from packages.data import data_providers
    # vraies trajectoires synthétiques (bruit réaliste → déclenche les entrées swing)
    t0 = datetime(2021, 1, 1, tzinfo=timezone.utc)
    data = {s: data_providers.create("synthetic", seed=3, drift=0.18, annual_vol=0.25)
            .fetch_ohlcv(s, "1d", t0, t0 + timedelta(days=500)) for s in ("AAA", "BBB", "CCC")}
    broker, jn, eq, ts = fast_swing_backtest(
        data, cash=10_000, max_positions=3, daily_max_loss=0.06, trail_atr=4.0,
        next_open_fills=True, close_at_end=True)
    assert len(eq) == max(len(b) for b in data.values()) and eq[-1] > 0
    assert len(jn.all()) >= 1                      # au moins un trade clôturé
    assert all(t.entry_ts is not None for t in jn.all())


def test_daily_max_loss_blocks_entries_on_crash():
    # krach continu → aucune tendance haussière → aucune entrée (et pas d'explosion)
    down = [100 - i * 0.4 for i in range(300)]
    data = {"AAA": _series("AAA", down)}
    broker, jn, eq, ts = fast_swing_backtest(
        data, cash=10_000, max_positions=5, trend=20, exit_trend=50,
        daily_max_loss=0.03, close_at_end=True)
    assert eq[-1] == 10_000 and not jn.all()       # jamais investi en tendance baissière
