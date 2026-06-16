"""Ratios financiers — esprit Vernimmen (rentabilité, levier, cash). Point-in-time."""

from __future__ import annotations

from packages.fundamentals.models import Financials

_TAX = 0.25


def _safe(n: float, d: float) -> float:
    return n / d if d else float("nan")


def gross_margin(f: Financials) -> float:
    return _safe(f.gross_profit, f.revenue)


def ebit_margin(f: Financials) -> float:
    return _safe(f.ebit, f.revenue)


def net_margin(f: Financials) -> float:
    return _safe(f.net_income, f.revenue)


def roe(f: Financials) -> float:
    return _safe(f.net_income, f.total_equity)


def roic(f: Financials) -> float:
    invested = f.total_equity + f.total_debt - f.cash
    return _safe(f.ebit * (1 - _TAX), invested)


def net_debt_to_ebitda(f: Financials) -> float:
    return _safe(f.total_debt - f.cash, f.ebitda)


def interest_coverage(f: Financials) -> float:
    return _safe(f.ebit, f.interest_expense) if f.interest_expense else float("inf")


def fcf_conversion(f: Financials) -> float:
    return _safe(f.fcf, f.ebitda)


def all_ratios(f: Financials) -> dict[str, float]:
    return {
        "gross_margin": gross_margin(f), "ebit_margin": ebit_margin(f),
        "net_margin": net_margin(f), "roe": roe(f), "roic": roic(f),
        "net_debt_ebitda": net_debt_to_ebitda(f),
        "interest_coverage": interest_coverage(f), "fcf_conversion": fcf_conversion(f),
    }
