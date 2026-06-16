"""Provider fondamental FMP (réel) → Financials. Implémente FundamentalsProvider.

Le fetch réseau (urllib, clé via env FMP_API_KEY) est isolé ; le mapping JSON→Financials
(`build_financials`) est pur et testable avec des fixtures. À utiliser en prod à la place
du SyntheticFundamentalsProvider. **Point-in-time** : on date par la `date` du dernier
état financier publié (à respecter strictement pour le ML — pas de révision a posteriori).
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone

from packages.fundamentals.models import Financials

_BASE = "https://financialmodelingprep.com/api/v3"


def _f(d: dict, *keys: str, default: float = 0.0) -> float:
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return default


def build_financials(symbol: str, income: dict, balance: dict,
                     cashflow: dict, profile: dict) -> Financials:
    """Mapping pur JSON FMP → Financials (dernier exercice). Défensif sur champs manquants."""
    date_str = income.get("date") or balance.get("date")
    as_of = (datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
             if date_str else datetime.now(timezone.utc))
    price = _f(profile, "price")
    shares = _f(income, "weightedAverageShsOutDil", "weightedAverageShsOut")
    if shares == 0 and price:
        shares = _f(profile, "mktCap") / price if _f(profile, "mktCap") else 0.0
    return Financials(
        symbol=symbol, as_of=as_of, sector=profile.get("sector", "Unknown"),
        price=price, shares=shares,
        revenue=_f(income, "revenue"),
        gross_profit=_f(income, "grossProfit"),
        ebit=_f(income, "operatingIncome", "ebit"),
        ebitda=_f(income, "ebitda"),
        net_income=_f(income, "netIncome"),
        total_equity=_f(balance, "totalStockholdersEquity", "totalEquity"),
        total_debt=_f(balance, "totalDebt"),
        cash=_f(balance, "cashAndCashEquivalents", "cashAndShortTermInvestments"),
        fcf=_f(cashflow, "freeCashFlow"),
        interest_expense=_f(income, "interestExpense"))


class FMPFundamentalsProvider:
    name = "fmp"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("FMP_API_KEY", "")

    def _get(self, path: str) -> list | dict:
        url = f"{_BASE}/{path}?apikey={self.api_key}&limit=1"
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())

    def get(self, symbol: str, as_of: datetime | None = None) -> Financials | None:
        try:
            income = (self._get(f"income-statement/{symbol}") or [{}])[0]
            balance = (self._get(f"balance-sheet-statement/{symbol}") or [{}])[0]
            cashflow = (self._get(f"cash-flow-statement/{symbol}") or [{}])[0]
            profile = (self._get(f"profile/{symbol}") or [{}])[0]
        except Exception:  # noqa: BLE001
            return None
        return build_financials(symbol, income, balance, cashflow, profile)
