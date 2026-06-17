"""Pont indicateurs étendu — le repli RSI maison doit fonctionner sans pandas-ta."""

from __future__ import annotations

from packages.indicators.extended import rsi


def test_rsi_hausse_continue_proche_100():
    closes = list(range(1, 40))            # série strictement croissante
    assert rsi(closes, period=14) > 90


def test_rsi_baisse_continue_proche_0():
    closes = list(range(40, 1, -1))        # série strictement décroissante
    assert rsi(closes, period=14) < 10


def test_rsi_serie_courte_neutre():
    assert rsi([1, 2, 3], period=14) == 50.0
