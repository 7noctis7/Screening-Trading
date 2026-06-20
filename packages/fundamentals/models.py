"""Modèles financiers point-in-time (Module 6). Stdlib only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Financials:
    symbol: str
    as_of: datetime
    sector: str
    price: float
    shares: float
    revenue: float
    gross_profit: float
    ebit: float
    ebitda: float
    net_income: float
    total_equity: float
    total_debt: float
    cash: float
    fcf: float
    interest_expense: float = 0.0
    revenue_growth: float | None = None       # croissance CA YoY RÉELLE (si fournie par la source)
    earnings_growth: float | None = None      # croissance bénéfices YoY RÉELLE (si fournie par la source)
    currency: str | None = None               # devise des ÉTATS FINANCIERS (ex. TWD pour TSM)
    price_currency: str | None = None         # devise du COURS (ex. USD pour l'ADR) — sert à convertir
