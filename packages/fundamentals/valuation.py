"""Valorisation — esprit Damodaran : multiples + DCF (FCFF) + marge de sécurité.

Multiples toujours à comparer aux comparables du secteur (fait dans le ranking
via z-score sector-neutral). Le DCF est volontairement simple (à raffiner) mais réel.
"""

from __future__ import annotations

from packages.fundamentals.models import Financials


def _safe(n: float, d: float) -> float:
    return n / d if d else float("nan")


def market_cap(f: Financials) -> float:
    return f.price * f.shares


def enterprise_value(f: Financials) -> float:
    return market_cap(f) + f.total_debt - f.cash


def per(f: Financials) -> float:
    return _safe(market_cap(f), f.net_income)


def ev_ebitda(f: Financials) -> float:
    return _safe(enterprise_value(f), f.ebitda)


def price_to_book(f: Financials) -> float:
    return _safe(market_cap(f), f.total_equity)


def ev_sales(f: Financials) -> float:
    return _safe(enterprise_value(f), f.revenue)


def earnings_yield(f: Financials) -> float:
    return _safe(f.net_income, market_cap(f))


def fcf_yield(f: Financials) -> float:
    return _safe(f.fcf, market_cap(f))


def dcf_intrinsic_per_share(f: Financials, wacc: float = 0.09, growth: float = 0.04,
                            terminal_growth: float = 0.02, years: int = 10) -> float:
    """DCF FCFF simplifié → valeur intrinsèque par action."""
    if f.fcf <= 0 or wacc <= terminal_growth or f.shares <= 0:
        return float("nan")
    pv = 0.0
    cf = f.fcf
    for t in range(1, years + 1):
        cf *= (1 + growth)
        pv += cf / (1 + wacc) ** t
    terminal = cf * (1 + terminal_growth) / (wacc - terminal_growth)
    pv += terminal / (1 + wacc) ** years
    equity_value = pv - (f.total_debt - f.cash)  # EV → equity
    return equity_value / f.shares


def margin_of_safety(f: Financials, **dcf_kwargs) -> float:
    """(valeur intrinsèque / prix) − 1. Positif = sous-évalué."""
    intrinsic = dcf_intrinsic_per_share(f, **dcf_kwargs)
    return intrinsic / f.price - 1.0 if (intrinsic == intrinsic and f.price) else float("nan")
