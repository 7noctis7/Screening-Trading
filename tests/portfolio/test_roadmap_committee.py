"""Roadmap comité : impact de marché (Almgren √) + DD-cible ajusté aux queues."""

from packages.execution.costs import market_impact_bps
from packages.portfolio.construction import tail_adjusted_dd_target


def test_market_impact_is_sqrt_and_monotone():
    assert market_impact_bps(0, 1e6) == 0.0
    small = market_impact_bps(1e5, 1e6, coef=10.0)
    big = market_impact_bps(4e5, 1e6, coef=10.0)
    # 4× la taille → 2× l'impact (loi en racine carrée), pas 4×
    assert abs(big / small - 2.0) < 1e-6


def test_market_impact_zero_adv():
    assert market_impact_bps(1e5, 0) == 0.0


def test_tail_adjust_shrinks_when_fat_tails():
    # queues gaussiennes (ratio ≤ 1.29) → inchangé
    assert tail_adjusted_dd_target(0.25, 1.2) == 0.25
    # queues épaisses → DD-cible réduit
    adj = tail_adjusted_dd_target(0.25, 2.0)
    assert adj < 0.25
    assert abs(adj - 0.25 * (1.29 / 2.0)) < 1e-9


def test_tail_adjust_handles_none():
    assert tail_adjusted_dd_target(0.25, None) == 0.25
