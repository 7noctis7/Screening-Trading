from packages.core.models import SignalDirection
from packages.strategies import strategies
from tests._helpers import mkbars


def test_swing_registered():
    assert "swing" in strategies


def test_swing_entry_on_pullback_in_uptrend():
    """Tendance haussière + repli RSI racheté → signal LONG avec stop/target ATR."""
    s = strategies.create("swing", trend=20, rsi_period=5, pullback=45.0)
    # montée régulière (tendance + SMA montante), puis petit creux racheté en fin de série
    prices = [100 + i for i in range(40)] + [138, 134, 139]  # repli puis reprise
    sigs = s.generate_signals(mkbars(prices))
    assert sigs and sigs[0].direction is SignalDirection.LONG
    assert sigs[0].stop is not None and sigs[0].target is not None
    assert sigs[0].target > sigs[0].stop


def test_swing_no_signal_when_flat_history():
    s = strategies.create("swing")
    assert s.generate_signals(mkbars([100.0] * 10)) == []  # historique trop court / plat
