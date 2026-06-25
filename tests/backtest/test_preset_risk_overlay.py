"""Tests overlay de risque câblé dans le preset (non-régression + effet en krach)."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np

from packages.backtest.preset_backtest import preset_backtest


def _bars(closes):
    base = datetime(2022, 1, 1)
    return [SimpleNamespace(ts=base + timedelta(days=i), close=float(c))
            for i, c in enumerate(closes)]


def _crash_data(n_sym=6, n=400, crash_at=320):
    """Univers corrélé : marche aléatoire douce puis krach (-3%/j) → drawdown."""
    rng = np.random.default_rng(0)
    data, acmap = {}, {}
    shock = rng.normal(0.0004, 0.008, n)            # facteur marché commun
    for k in range(n_sym):
        idio = rng.normal(0, 0.004, n)
        r = shock + idio
        r[crash_at:crash_at + 30] -= 0.03              # krach corrélé
        closes = 100 * np.cumprod(1 + r)
        sym = f"S{k}"
        data[sym] = _bars(closes)
        acmap[sym] = "equity"
    return data, acmap


def test_overlay_off_is_default_and_available():
    data, acmap = _crash_data()
    base = preset_backtest(data, asset_classes=acmap)
    explicit_off = preset_backtest(data, asset_classes=acmap, risk_overlay=False)
    assert base["available"] and explicit_off["available"]
    # défaut == explicitement OFF (non-régression) : mêmes métriques preset
    assert base["preset"] == explicit_off["preset"]
    assert base["avg_gross"] == explicit_off["avg_gross"]


def test_overlay_on_reduces_drawdown_and_gross_in_crash():
    data, acmap = _crash_data()
    off = preset_backtest(data, asset_classes=acmap, risk_overlay=False)
    on = preset_backtest(data, asset_classes=acmap, risk_overlay=True)
    assert on["available"]
    # le taper réduit l'exposition moyenne et adoucit le drawdown
    assert on["avg_gross"] <= off["avg_gross"]
    assert on["preset"]["max_drawdown"] >= off["preset"]["max_drawdown"]
