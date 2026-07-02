"""Net-expectancy entry filter (replaces the naive R:R >= 2 rule).

E[R] = p*RR - (1-p) - costs_in_R. A 2:1 setup at p=0.30 loses;
a 1.5:1 at p=0.55 is excellent. p must come from a CALIBRATED model."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SetupDecision:
    accept: bool
    expectancy_R: float
    reason: str


def net_expectancy(p_calibrated: float, rr: float, cost_R: float) -> float:
    return p_calibrated * rr - (1.0 - p_calibrated) - cost_R


def evaluate_setup(p_calibrated: float, rr: float, cost_R: float = 0.05,
                   min_expectancy: float = 0.10,
                   min_rr: float = 1.0) -> SetupDecision:
    if rr < min_rr:
        return SetupDecision(False, 0.0, f"RR {rr:.2f} < floor {min_rr}")
    e = net_expectancy(p_calibrated, rr, cost_R)
    if e < min_expectancy:
        return SetupDecision(False, e, f"E={e:.2f}R < {min_expectancy}R")
    return SetupDecision(True, e, f"E={e:.2f}R (p={p_calibrated:.2f}, RR={rr:.1f})")
