"""Tests des signaux d'alpha overnight + momentum time-series (factor_calcs)."""

from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.models import Bar
from packages.ranking.factors import FactorContext, factor_calcs


def _bars(closes, opens, symbol="X"):
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    return [Bar(symbol, "1d", t0 + timedelta(days=i), o, max(o, c) * 1.01,
                min(o, c) * 0.99, c, 1000.0)
            for i, (o, c) in enumerate(zip(opens, closes, strict=False))]


def test_registered():
    assert "overnight" in factor_calcs and "ts_momentum" in factor_calcs


def test_overnight_positive_when_gaps_up():
    # chaque open > close de la veille → overnight return positif
    closes = [100.0] * 80
    opens = [101.0] * 80                       # gap +1% chaque nuit
    panel = {"X": _bars(closes, opens, "X")}
    out = factor_calcs.create("overnight").values(FactorContext(panel, 79))
    assert out["X"] > 0.0


def test_overnight_negative_when_gaps_down():
    closes = [100.0] * 80
    opens = [99.0] * 80
    out = factor_calcs.create("overnight").values(
        FactorContext({"X": _bars(closes, opens)}, 79))
    assert out["X"] < 0.0


def test_ts_momentum_sign_follows_trend():
    up = list(np.linspace(50, 150, 120))
    down = list(np.linspace(150, 50, 120))
    panel = {"UP": _bars(up, up, "UP"), "DOWN": _bars(down, down, "DOWN")}
    out = factor_calcs.create("ts_momentum").values(FactorContext(panel, 119))
    assert out["UP"] > 0.0 and out["DOWN"] < 0.0


def test_ts_momentum_nan_when_short():
    short = [100.0] * 10
    out = factor_calcs.create("ts_momentum").values(
        FactorContext({"X": _bars(short, short)}, 9))
    assert out["X"] != out["X"]                 # NaN (série < window+1)
