"""Band rebalancing: trade only positions outside their tolerance band.
Cuts turnover 50-70% vs calendar rebalancing; costs are performance."""
from __future__ import annotations

import pandas as pd


def bands(targets: pd.Series, vols: pd.Series, k: float = 0.25,
          min_band: float = 0.01) -> pd.Series:
    rel = vols / max(vols.mean(), 1e-9)
    return (k * targets * rel).clip(lower=min_band)


def rebalance_orders(current: pd.Series, targets: pd.Series,
                     vols: pd.Series, k: float = 0.25,
                     cost_bps: float = 10.0,
                     risk_gain_bps: float | None = None) -> pd.Series:
    """Weight deltas for assets breaching their band (back to target).
    If risk_gain_bps is given, skip trades whose expected risk benefit
    does not cover estimated cost."""
    b = bands(targets, vols, k)
    dev = current - targets
    breach = dev.abs() > b
    orders = (-dev).where(breach, 0.0)
    if risk_gain_bps is not None:
        est_cost = orders.abs() * cost_bps
        orders = orders.where(est_cost <= risk_gain_bps, 0.0)
    return orders
