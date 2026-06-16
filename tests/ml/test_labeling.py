import numpy as np
from packages.ml import triple_barrier, meta_labels, ewm_volatility


def test_profit_barrier_hit():
    close = np.array([100.0, 103.0, 104.0])
    lab = triple_barrier(close, [0], pt=2, sl=2, vol=0.01, horizon=5)[0]
    assert lab.touched == "pt" and lab.label == 1


def test_stop_barrier_hit():
    close = np.array([100.0, 97.0, 96.0])
    lab = triple_barrier(close, [0], pt=2, sl=2, vol=0.01, horizon=5)[0]
    assert lab.touched == "sl" and lab.label == -1


def test_time_barrier_neutral():
    close = np.array([100.0, 100.0, 100.0])
    lab = triple_barrier(close, [0], pt=2, sl=2, vol=0.01, horizon=2)[0]
    assert lab.touched == "time" and lab.label == 0


def test_meta_labels_winner_logic():
    close = np.array([100.0, 103.0])
    labs = triple_barrier(close, [0], pt=2, sl=2, vol=0.01, horizon=2)
    assert meta_labels(labs, side=1)[0] == 1     # long gagnant
    assert meta_labels(labs, side=-1)[0] == 0    # short perdant


def test_ewm_volatility_positive():
    close = np.cumprod(1 + np.random.default_rng(0).normal(0, 0.01, 100)) * 100
    assert (ewm_volatility(close)[1:] >= 0).all()
