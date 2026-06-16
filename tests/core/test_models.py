from datetime import datetime, timezone

import pytest

from packages.core.models import Position, Side, Signal, SignalDirection


def test_position_unrealized_pnl_long():
    p = Position("AAPL", Side.LONG, qty=10, avg_price=100.0)
    assert p.unrealized_pnl(mark=110.0) == 100.0


def test_position_unrealized_pnl_short():
    p = Position("AAPL", Side.SHORT, qty=10, avg_price=100.0)
    assert p.unrealized_pnl(mark=90.0) == 100.0


def test_signal_reward_risk():
    s = Signal(
        "BTC/USDT", SignalDirection.LONG, "x",
        ts=datetime.now(timezone.utc), stop=90, target=130,
    )
    # entrée de référence = (90+130)/2 = 110 ; risque=20 ; gain=20 → R:R=1.0
    assert s.reward_risk == pytest.approx(1.0)


def test_signal_reward_risk_none_without_levels():
    s = Signal("AAPL", SignalDirection.LONG, "x", ts=datetime.now(timezone.utc))
    assert s.reward_risk is None
