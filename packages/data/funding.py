"""Funding rate des perpétuels crypto (Binance + repli Bybit) — lecture publique, 0 €.

Thèse : un funding TRÈS positif = longs sur-payent (positionnement long sur-tendu) →
biais de reversion à la baisse ; funding très négatif = shorts sur-tendus → reversion
haussière. Marché moins efficient que les actions. API publiques, AUCUNE clé pour la
data. Best-effort (réseau absent → []). Parsing séparé du réseau (testable hors-ligne).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

_BINANCE = ("https://fapi.binance.com/fapi/v1/fundingRate"
            "?symbol={sym}USDT&limit={limit}")
_BYBIT = ("https://api.bybit.com/v5/market/funding/history"
          "?category=linear&symbol={sym}USDT&limit={limit}")


def _get_json(url: str, timeout: float = 8.0) -> Any:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-terminal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - best-effort
        return None


def _parse_binance(data: Any) -> list[dict]:
    """Binance fundingRate → [{ts_ms, rate}] trié croissant (testable)."""
    out: list[dict] = []
    for r in data or []:
        try:
            out.append({"ts_ms": int(r["fundingTime"]),
                        "rate": float(r["fundingRate"])})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda x: x["ts_ms"])


def _parse_bybit(data: Any) -> list[dict]:
    """Bybit funding/history → [{ts_ms, rate}] trié croissant (testable)."""
    rows = (((data or {}).get("result", {}) or {}).get("list", []) or [])
    out: list[dict] = []
    for r in rows:
        try:
            out.append({"ts_ms": int(r["fundingRateTimestamp"]),
                        "rate": float(r["fundingRate"])})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda x: x["ts_ms"])


def fetch_funding(symbol: str = "BTC", limit: int = 1000) -> list[dict]:
    """Historique funding (Binance, repli Bybit). [{ts_ms, rate}]. [] si réseau KO."""
    sym = symbol.upper().replace("-USD", "").replace("USDT", "")
    out = _parse_binance(_get_json(_BINANCE.format(sym=sym, limit=min(limit, 1000))))
    if out:
        return out
    return _parse_bybit(_get_json(_BYBIT.format(sym=sym, limit=min(limit, 200))))


def daily_funding(records: list[dict]) -> dict:
    """Agrège le funding (3×/j à 8h) en coût QUOTIDIEN {date: somme_rate}."""
    from datetime import UTC, datetime
    out: dict = {}
    for r in records:
        d = datetime.fromtimestamp(r["ts_ms"] / 1000, UTC).date()
        out[d] = out.get(d, 0.0) + r["rate"]
    return out
