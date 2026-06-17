"""FundamentalsProvider — interface + provider synthétique déterministe (offline).

Le provider RÉEL (FMP/yfinance) s'implémente via la même interface dans son fichier,
en respectant le POINT-IN-TIME (états financiers tels que publiés à l'époque).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from packages.fundamentals.models import Financials

_SECTORS = ["Information Technology", "Health Care", "Financials", "Industrials",
            "Consumer Staples", "Energy", "Materials", "Utilities"]


@runtime_checkable
class FundamentalsProvider(Protocol):
    def get(self, symbol: str, as_of: datetime | None = None) -> Financials | None: ...


def degrade_prior(f: Financials, factor: float = 0.90) -> Financials:
    """Construit un exercice N-1 plausible (légèrement dégradé) → calcul des variations YoY.

    Sert au Piotroski complet quand le provider ne fournit pas l'historique (synthétique).
    """
    from dataclasses import replace
    return replace(f, revenue=f.revenue * factor, gross_profit=f.gross_profit * factor * 0.97,
                   ebit=f.ebit * factor * 0.95, ebitda=f.ebitda * factor * 0.96,
                   net_income=f.net_income * factor * 0.92, fcf=f.fcf * factor * 0.9,
                   total_equity=f.total_equity * 0.96, total_debt=f.total_debt * 1.05,
                   shares=f.shares * 0.995)


class SyntheticFundamentalsProvider:
    """Fondamentaux déterministes par symbole (hashlib, jamais hash() builtin)."""

    name = "synthetic_fundamentals"

    def get(self, symbol: str, as_of: datetime | None = None) -> Financials:
        h = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
        r = (h % 1000) / 1000.0  # [0,1) stable
        revenue = 1e9 * (1 + 9 * r)
        gm = 0.25 + 0.5 * ((h >> 3) % 100) / 100
        ebit_m = 0.08 + 0.22 * ((h >> 5) % 100) / 100
        net_m = ebit_m * (0.6 + 0.3 * r)
        ebitda = revenue * (ebit_m + 0.05)
        equity = revenue * (0.4 + 0.8 * r)
        debt = revenue * (0.1 + 1.2 * ((h >> 7) % 100) / 100)
        return Financials(
            symbol=symbol, as_of=as_of or datetime.now(timezone.utc),
            sector=_SECTORS[h % len(_SECTORS)],
            price=20 + 180 * r, shares=revenue / (50 + 100 * r),
            revenue=revenue, gross_profit=revenue * gm, ebit=revenue * ebit_m,
            ebitda=ebitda, net_income=revenue * net_m, total_equity=equity,
            total_debt=debt, cash=revenue * 0.1 * r, fcf=revenue * net_m * (0.7 + 0.5 * r),
            interest_expense=debt * 0.04)

    def get_prior(self, symbol: str, as_of: datetime | None = None) -> Financials:
        """Exercice N-1 avec une croissance PROPRE à chaque société (déterministe) → la croissance
        CA/bénéfices varie d'un titre à l'autre (corrige le taux constant)."""
        from dataclasses import replace
        f = self.get(symbol)
        h = int(hashlib.sha256((symbol + "|prev").encode()).hexdigest()[:8], 16)
        g_rev = -0.10 + (h % 60) / 100.0            # croissance CA ∈ [-10 %, +49 %], par titre
        g_ni = -0.25 + ((h >> 6) % 95) / 100.0      # croissance bénéfices ∈ [-25 %, +69 %]
        g_gm = ((h >> 12) % 8) / 100.0              # amélioration de marge brute (0-7 pts)
        gm_now = f.gross_profit / f.revenue if f.revenue else 0.3
        denr, denn = (1 + g_rev) or 1.0, (1 + g_ni) or 1.0
        prev_rev = f.revenue / denr
        prev_ni = f.net_income / denn if (f.net_income > 0 and denn > 0) else f.net_income * 1.05
        return replace(
            f, revenue=prev_rev, gross_profit=prev_rev * max(0.05, gm_now - g_gm),
            ebit=f.ebit / denr, ebitda=f.ebitda / denr, net_income=prev_ni,
            total_equity=f.total_equity * 0.95, total_debt=f.total_debt * 1.04,
            cash=f.cash * 0.9, fcf=(f.fcf / denn if (f.fcf > 0 and denn > 0) else f.fcf * 1.05),
            shares=f.shares * 0.99)
