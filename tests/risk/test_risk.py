from datetime import datetime, timezone
from packages.core.models import Order, Side, Signal, SignalDirection
from packages.risk import RiskEngine, risk_rules


def _order(qty=10, price=100):
    return Order("X", Side.LONG, qty, limit_price=price)


def _sig(stop, target):
    return Signal("X", SignalDirection.LONG, "s", datetime.now(timezone.utc),
                  stop=stop, target=target, features={"ref_price": 100})


def test_reward_risk_veto():
    rule = risk_rules.create("reward_risk", min_rr=2.0)
    bad = rule.check(_order(), [], 100_000, signal=_sig(stop=95, target=105))
    assert not bad.approved  # R:R = 1.0 < 2.0
    good = rule.check(_order(), [], 100_000, signal=_sig(stop=95, target=115))
    assert good.approved  # R:R = 3.0


def test_kill_switch_blocks():
    eng = RiskEngine([], max_daily_drawdown_pct=0.05)
    eng.new_day(100_000)
    eng.mark_equity(94_000)  # -6 % > 5 %
    assert eng.kill_switch
    assert not eng.approve(_order(), [], 94_000).approved


def test_max_positions():
    from packages.core.models import Position
    rule = risk_rules.create("max_positions", max_positions=1)
    held = [Position("Y", Side.LONG, 1, 50)]
    assert not rule.check(_order(), held, 100_000).approved
