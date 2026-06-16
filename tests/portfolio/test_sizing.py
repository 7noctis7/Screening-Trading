from datetime import datetime, timezone
from packages.core.models import Signal, SignalDirection
from packages.portfolio.sizing import sizers


def _sig(stop, atr):
    return Signal("X", SignalDirection.LONG, "s", datetime.now(timezone.utc),
                  stop=stop, target=stop + 10, features={"atr": atr})


def test_fixed_fractional_risk():
    sz = sizers.create("fixed_fractional", max_risk_pct=0.01)
    qty = sz.size(_sig(stop=90, atr=2), equity=100_000, price=100)
    # risque/unité = 10 ; budget = 1000 → 100 unités
    assert abs(qty - 100) < 1e-6


def test_vol_target_caps_at_max_frac():
    sz = sizers.create("vol_target", target_annual_vol=10.0, max_capital_frac=0.10)
    qty = sz.size(_sig(stop=90, atr=2), equity=100_000, price=100)
    # cible énorme → bridé au plafond 10 % du capital → 100 unités
    assert abs(qty - 100) < 1e-6


def test_no_stop_no_size():
    s = Signal("X", SignalDirection.LONG, "s", datetime.now(timezone.utc))
    assert sizers.create("fixed_fractional").size(s, 100_000, 100) == 0.0
