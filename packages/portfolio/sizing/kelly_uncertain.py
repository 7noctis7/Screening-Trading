"""Fractional Kelly under parameter uncertainty.

Pure Kelly assumes p and payoff are KNOWN. They are estimated with error;
we (1) shrink p toward 0.5 by its standard error, (2) apply a fraction.
Not caution - the correct Kelly given estimation risk."""
from __future__ import annotations

import math


def shrunk_p(p_hat: float, n_trades: int, z: float = 1.0) -> float:
    if n_trades <= 0:
        return 0.5
    se = math.sqrt(max(p_hat * (1 - p_hat), 1e-9) / n_trades)
    return max(0.0, min(1.0, p_hat - z * se))


def kelly_fraction(p: float, payoff_ratio: float) -> float:
    if payoff_ratio <= 0:
        return 0.0
    return p - (1 - p) / payoff_ratio


def sized_kelly(p_hat: float, payoff_ratio: float, n_trades: int,
                fraction: float = 0.25, cap: float = 0.05) -> float:
    """Quarter-Kelly on the shrunk estimate, hard-capped. Never negative."""
    f = kelly_fraction(shrunk_p(p_hat, n_trades), payoff_ratio)
    return float(max(0.0, min(f * fraction, cap)))
