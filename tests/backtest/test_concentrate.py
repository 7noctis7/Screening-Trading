"""Concentration du portefeuille : la poussière est éliminée, l'investi préservé."""
import numpy as np

from packages.backtest.preset_backtest import _concentrate


def test_drops_dust_and_preserves_gross():
    w = np.array([0.50, 0.30, 0.015, 0.010, 0.005])   # 3 dernières = poussière (<2,5 %)
    out = _concentrate(w, 0.025)
    assert (out[2:] == 0).all()                        # poussière éliminée
    assert abs(out.sum() - w.sum()) < 1e-9             # gross investi inchangé (redistribué)
    assert out[0] > w[0] and out[1] > w[1]             # redistribué aux survivants


def test_noop_when_all_above_floor():
    w = np.array([0.6, 0.4])
    assert np.allclose(_concentrate(w, 0.025), w)


def test_handles_empty_and_zero():
    assert _concentrate(np.zeros(3), 0.025).sum() == 0
