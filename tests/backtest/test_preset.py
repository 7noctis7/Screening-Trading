"""Backtest du preset stratégique (qualité + risk-parity + DD-target + blackout + band)."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from packages.backtest.preset_backtest import preset_backtest


@dataclass
class Bar:
    ts: datetime
    close: float


def _series(n: int, drift: float, vol: float, seed: int) -> list[Bar]:
    import random
    rng = random.Random(seed)
    px, out, t0 = 100.0, [], datetime(2020, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        px *= math.exp(drift / 252 + vol / math.sqrt(252) * rng.gauss(0, 1))
        out.append(Bar(t0 + timedelta(days=i), px))
    return out


def _data(n=400):
    return {f"S{i}": _series(n, 0.08 + 0.01 * (i % 5), 0.18 + 0.02 * (i % 4), seed=i) for i in range(12)}


def test_preset_runs_and_reports():
    data = _data()
    quality = {s: float(i) for i, s in enumerate(data)}          # qualité statique arbitraire
    res = preset_backtest(data, quality, top_k=8, step=21, lookback=120)
    assert res["available"]
    assert res["preset"]["available"] and res["benchmark"]["available"]
    assert 0.0 <= res["avg_gross"] <= 1.0                        # jamais de levier
    assert res["turnover_annual"] >= 0.0


def test_dd_target_caps_exposure():
    data = _data()
    quality = {s: 1.0 for s in data}
    tight = preset_backtest(data, quality, top_k=8, dd_target=0.05)   # DD serré → exposition réduite
    loose = preset_backtest(data, quality, top_k=8, dd_target=0.40)
    assert tight["avg_gross"] <= loose["avg_gross"] + 1e-9


def test_degrades_when_too_few_assets():
    data = {"A": _series(400, 0.08, 0.18, 1)}
    assert preset_backtest(data, {"A": 1.0})["available"] is False
