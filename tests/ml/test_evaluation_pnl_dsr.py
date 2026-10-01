"""Smoke: pont ML → PnL/DSR (mesure seule)."""
from __future__ import annotations

import numpy as np

from packages.ml.evaluation_pnl_dsr import (
    evaluate_oos_with_dsr,
    strategy_returns_from_meta,
)


def test_strategy_returns_meta_gate():
    y = np.array([1, 0, 1, 1])
    r = np.array([0.01, -0.02, 0.03, -0.01])
    out = strategy_returns_from_meta(y, r, side=1)
    np.testing.assert_allclose(out, [0.01, 0.0, 0.03, -0.01])


def test_evaluate_oos_with_dsr_shape():
    y_true = np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0] * 5)
    y_pred = np.array([1, 0, 1, 0, 0, 1, 0, 1, 0, 0] * 5)
    rets = np.linspace(-0.02, 0.03, len(y_true))
    rep = evaluate_oos_with_dsr(y_true, y_pred, rets, n_trials=5)
    assert "accuracy" in rep and "dsr" in rep
    assert rep["n"] == len(y_true)
    assert "pnl_sum" in rep
