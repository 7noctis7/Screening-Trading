"""Provider fondamental **yfinance** (réel, GRATUIT, sans clé) → Financials.

Alternative gratuite à FMP : Yahoo Finance via `yfinance`. Couvre la plupart des actions/ETF.
Plus lent que FMP (1 requête réseau par actif) → on l'utilise sur un sous-ensemble pertinent
(positions + watchlist). Import paresseux : aucune dépendance tant que non utilisé.

Activation : `export QUANT_FUND=yf` (sinon FMP si clé, sinon synthétique).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from packages.fundamentals.models import Financials

# Cache disque (le cron quotidien le réchauffe → builds suivants instantanés). TTL 24 h.
_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "yf_fundamentals"
_CACHE_TTL = 86_400.0


def _cache_get(symbol: str) -> dict | None:
    p = _CACHE_DIR / f"{symbol.replace('/', '_')}.json"
    try:
        if p.exists() and time.time() - p.stat().st_mtime < _CACHE_TTL:
            return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None
    return None


def _cache_put(symbol: str, info: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        keep = {k: info.get(k) for k in (
            "currentPrice", "regularMarketPrice", "totalRevenue", "netIncomeToCommon", "ebitda",
            "sharesOutstanding", "marketCap", "grossMargins", "ebit", "totalStockholderEquity",
            "totalDebt", "totalCash", "freeCashflow", "sector")}
        (_CACHE_DIR / f"{symbol.replace('/', '_')}.json").write_text(json.dumps(keep))
    except Exception:  # noqa: BLE001
        pass


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
        info = _cache_get(symbol)
        if info is None:
            try:
                import yfinance as yf
                info = yf.Ticker(symbol).info or {}
                _cache_put(symbol, info)
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
