"""Tests backtest PEAD portefeuille net de coûts + métriques (hors-ligne)."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np

from packages.strategies.pead_portfolio import pead_daily_returns, pead_metrics


def _bars(closes):
    base = datetime(2024, 1, 1)
    return [SimpleNamespace(ts=base + timedelta(days=i), close=c)
            for i, c in enumerate(closes)]


def _drift_series():
    """120 barres : gap +3 % à J50 puis dérive +0,5 %/j sur 21 j (PEAD haussier net)."""
    closes = [100.0] * 50
    closes.append(103.0)                       # J50 : réaction +3 %
    c = 103.0
    for _ in range(40):
        c *= 1.005                             # dérive post-annonce
        closes.append(c)
    closes += [c] * (120 - len(closes))
    ed = (datetime(2024, 1, 1) + timedelta(days=50)).date()
    return {"X": _bars(closes)}, {"X": [ed]}


def test_pead_daily_returns_capture_positive_drift():
    data, earn = _drift_series()
    _, rets = pead_daily_returns(data, earn, hold=21, cost_bps=0.0)
    assert rets.size > 0 and rets.mean() > 0          # la dérive est captée


def test_cost_reduces_pnl():
    data, earn = _drift_series()
    _, free = pead_daily_returns(data, earn, hold=21, cost_bps=0.0)
    _, costed = pead_daily_returns(data, earn, hold=21, cost_bps=50.0)
    assert costed.sum() < free.sum()                  # le coût ronge le PnL


def test_no_events_empty():
    data, _ = _drift_series()
    days, rets = pead_daily_returns(data, {"X": []}, hold=21)
    assert days == [] and rets.size == 0


def test_metrics_dsr_high_for_clean_edge_low_for_noise():
    edge = np.full(300, 0.001) + np.random.default_rng(0).normal(0, 0.0005, 300)
    noise = np.random.default_rng(1).normal(0, 0.01, 300)
    m_edge = pead_metrics(edge, n_trials=10)
    m_noise = pead_metrics(noise, n_trials=10)
    assert m_edge["dsr"] > 0.9 and m_noise["dsr"] < 0.5
    assert pead_metrics(np.ones(5))["available"] is False   # n<20
