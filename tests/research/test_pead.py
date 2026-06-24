"""Tests du signal PEAD (post-earnings drift)."""

from datetime import UTC, date, datetime, timedelta

from packages.core.models import Bar
from packages.research.pead import pead_signal


def _bars(closes, start=date(2024, 1, 1)):
    t0 = datetime(start.year, start.month, start.day, tzinfo=UTC)
    return [Bar("X", "1d", t0 + timedelta(days=i), c, c, c, c, 1000.0)
            for i, c in enumerate(closes)]


def test_drift_since_recent_earnings():
    # close=100 à l'annonce (jour 40) puis dérive +1/j → +10% au jour 50
    closes = [100.0] * 41 + [100.0 + i for i in range(1, 21)]  # dérive
    bars = _bars(closes)
    e = date(2024, 1, 1) + timedelta(days=40)
    sig = pead_signal(bars, [e], t=50, drift_window=20)
    assert abs(sig - 0.10) < 1e-6               # 110/100 - 1


def test_nan_when_no_recent_earnings():
    bars = _bars([100.0] * 60)
    old = date(2024, 1, 1)              # annonce trop ancienne
    assert pead_signal(bars, [old], t=59, drift_window=20) != \
        pead_signal(bars, [old], t=59, drift_window=20) or True
    import math
    assert math.isnan(pead_signal(bars, [old], t=59, drift_window=20))


def test_nan_without_events():
    import math
    assert math.isnan(pead_signal(_bars([100.0] * 30), []))
