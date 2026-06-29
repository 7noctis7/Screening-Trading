"""Historiques crypto gratuits (sans clé) — pour TESTER au gate, pas pour décider.

Sépare strictement parsers PURS (testables hors-ligne) et accès réseau (best-effort).
Sources avec un vrai historique gratuit :
  • Fear & Greed  : alternative.me /fng?limit=0          → quotidien depuis févr. 2018
  • Prix BTC      : CoinGecko /coins/bitcoin/market_chart → quotidien (days=max)
  • TVL DeFi      : DefiLlama /v2/historicalChainTvl      → quotidien multi-années
Les autres champs du cockpit (catégories, trending, peg) sont des SNAPSHOTS sans
historique gratuit → non éligibles au ML. Aucun chiffre inventé : [] si la source tombe.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import Any

_FNG = "https://api.alternative.me/fng/?limit=0&format=json"
_BTC = ("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        "?vs_currency=usd&days=max&interval=daily")
_TVL = "https://api.llama.fi/v2/historicalChainTvl"


def _get_json(url: str, timeout: float = 30.0) -> Any:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-terminal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _day(ts: Any, unit: str) -> str | None:
    """Timestamp epoch (s ou ms) → date ISO 'YYYY-MM-DD' (UTC). None si invalide."""
    try:
        sec = float(ts) / (1000.0 if unit == "ms" else 1.0)
        return datetime.fromtimestamp(sec, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def parse_fng_history(data: Any) -> list[tuple[str, float]]:
    """/fng → [(date, value 0-100)] trié croissant. Dédoublonne par jour (dernier)."""
    out: dict[str, float] = {}
    for row in ((data or {}).get("data") or []):
        d = _day(row.get("timestamp"), "s")
        try:
            v = float(row.get("value"))
        except (TypeError, ValueError):
            v = None
        if d and v is not None:
            out[d] = v
    return sorted(out.items())


def parse_market_chart(data: Any) -> list[tuple[str, float]]:
    """CoinGecko market_chart → [(date, close)] trié. Garde le dernier prix du jour."""
    out: dict[str, float] = {}
    for pair in ((data or {}).get("prices") or []):
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        d = _day(pair[0], "ms")
        try:
            v = float(pair[1])
        except (TypeError, ValueError):
            v = None
        if d and v is not None:
            out[d] = v
    return sorted(out.items())


def parse_tvl_history(data: Any) -> list[tuple[str, float]]:
    """DefiLlama historicalChainTvl → [(date, tvl)] trié croissant."""
    out: dict[str, float] = {}
    for row in (data or []):
        d = _day((row or {}).get("date"), "s")
        try:
            v = float(row.get("tvl"))
        except (TypeError, ValueError):
            v = None
        if d and v is not None:
            out[d] = v
    return sorted(out.items())


def fng_history() -> list[tuple[str, float]]:
    return parse_fng_history(_get_json(_FNG))


def btc_price_history() -> list[tuple[str, float]]:
    return parse_market_chart(_get_json(_BTC))


def tvl_history() -> list[tuple[str, float]]:
    return parse_tvl_history(_get_json(_TVL))


def align(a: list[tuple[str, float]],
          b: list[tuple[str, float]]) -> tuple[list[str], list[float], list[float]]:
    """Jointure interne sur les dates communes → (dates, vals_a, vals_b) alignés."""
    db = dict(b)
    dates, va, vb = [], [], []
    for d, x in a:
        if d in db:
            dates.append(d)
            va.append(x)
            vb.append(db[d])
    return dates, va, vb
