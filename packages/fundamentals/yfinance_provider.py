"""Provider fondamental **yfinance** (réel, GRATUIT, sans clé) → Financials.

Alternative gratuite à FMP : Yahoo Finance via `yfinance`. Couvre la plupart des actions/ETF.
Plus lent que FMP (1 requête réseau par actif) → on l'utilise sur un sous-ensemble pertinent
(positions + watchlist). Import paresseux : aucune dépendance tant que non utilisé.

Activation : `export QUANT_FUND=yf` (sinon FMP si clé, sinon synthétique).
"""

from __future__ import annotations

from datetime import datetime, timezone

from packages.fundamentals.models import Financials


def _f(info: dict, *keys: str, default: float = 0.0) -> float:
    for k in keys:
        v = info.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return default


class YFinanceFundamentalsProvider:
    name = "yfinance"

    def get(self, symbol: str, as_of: datetime | None = None) -> Financials | None:
        try:
            import yfinance as yf
            info = yf.Ticker(symbol).info or {}
        except Exception:  # noqa: BLE001
            return None
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            return None
        price = _f(info, "currentPrice", "regularMarketPrice")
        revenue = _f(info, "totalRevenue")
        net_income = _f(info, "netIncomeToCommon")
        ebitda = _f(info, "ebitda")
        shares = _f(info, "sharesOutstanding") or (_f(info, "marketCap") / price if price else 0.0)
        gross_margin = _f(info, "grossMargins")
        return Financials(
            symbol=symbol, as_of=as_of or datetime.now(timezone.utc),
            sector=info.get("sector", "Unknown"), price=price, shares=shares,
            revenue=revenue, gross_profit=revenue * gross_margin if gross_margin else 0.0,
            ebit=_f(info, "ebit") or ebitda * 0.85, ebitda=ebitda, net_income=net_income,
            total_equity=_f(info, "totalStockholderEquity") or revenue * 0.5,
            total_debt=_f(info, "totalDebt"), cash=_f(info, "totalCash"),
            fcf=_f(info, "freeCashflow"), interest_expense=0.0)
