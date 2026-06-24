"""Connecteur marchés de prédiction (Kalshi + Polymarket) — lecture seule, sans clé.

Les probas de marché (Fed, CPI, élections) agrègent la sagesse des foules et pricent
souvent les events macro plus vite que les modèles factoriels lents. Lues via les API
PUBLIQUES (aucune clé pour la data). Best-effort : réseau absent → listes vides, jamais
bloquant. Parsing séparé du réseau (testable hors-ligne). Aucune exécution d'ordre.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

_POLY_URL = "https://gamma-api.polymarket.com/markets?closed=false&limit={limit}"
_KALSHI_URL = "https://api.elections.kalshi.com/trade-api/v2/markets?status=open&limit={limit}"


def _get_json(url: str, timeout: float = 6.0) -> Any:
    """GET JSON best-effort (stdlib). None sur toute erreur (réseau, parse, timeout)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-terminal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URLs publiques fixes
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - best-effort, jamais bloquant
        return None


def _parse_polymarket(data: Any) -> list[dict]:
    """Normalise Gamma Polymarket → [{source, question, probability, end}]."""
    out: list[dict] = []
    for m in data or []:
        prices = m.get("outcomePrices")
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except json.JSONDecodeError:
                prices = None
        prob = None
        if isinstance(prices, list) and prices:
            try:
                prob = round(float(prices[0]), 4)
            except (TypeError, ValueError):
                prob = None
        q = m.get("question") or m.get("title")
        if q and prob is not None:
            out.append({"source": "polymarket", "question": q,
                        "probability": prob, "end": m.get("endDate")})
    return out


def _parse_kalshi(data: Any) -> list[dict]:
    """Normalise Kalshi → [{source, question, probability, end}] (prix en cents)."""
    out: list[dict] = []
    for m in (data or {}).get("markets", []):
        price = m.get("last_price") or m.get("yes_bid")
        prob = (round(float(price) / 100.0, 4)
                if isinstance(price, (int, float)) else None)
        q = m.get("title") or m.get("ticker")
        if q and prob is not None:
            out.append({"source": "kalshi", "question": q,
                        "probability": prob, "end": m.get("close_time")})
    return out


def fetch_markets(limit: int = 50) -> list[dict]:
    """Probas publiques agrégées (Polymarket + Kalshi). [] si réseau indispo."""
    poly = _parse_polymarket(_get_json(_POLY_URL.format(limit=limit)))
    kalshi = _parse_kalshi(_get_json(_KALSHI_URL.format(limit=limit)))
    return poly + kalshi


def implied_probability(records: list[dict], keyword: str) -> float | None:
    """Proba du 1er marché dont la question contient `keyword` (insensible casse).
    Feature macro forward-looking (ex. 'fed', 'recession'). None si absent."""
    kw = keyword.lower()
    for r in records:
        if kw in str(r.get("question", "")).lower():
            return r.get("probability")
    return None
