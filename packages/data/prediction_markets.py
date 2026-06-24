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

_POLY_URL = ("https://gamma-api.polymarket.com/markets?closed=false&active=true"
             "&order=volume24hr&ascending=false&limit={limit}")
_KALSHI_URL = "https://api.elections.kalshi.com/trade-api/v2/markets?status=open&limit={limit}"

# Mots-clés MACRO (label → variantes) : events macro qui bougent les actifs.
MACRO_KEYWORDS: dict[str, list[str]] = {
    "fed_rate_cut": ["fed", "rate cut", "fomc", "interest rate"],
    "cpi_inflation": ["cpi", "inflation"],
    "recession": ["recession"],
    "unemployment": ["unemployment", "jobs report", "nonfarm"],
    "gov_shutdown": ["shutdown"],
}
# Noms crypto courants (ticker → terme cherché dans les questions).
_CRYPTO_NAMES: dict[str, str] = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "xrp",
    "DOGE": "dogecoin", "ADA": "cardano",
}


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


def fetch_markets(limit: int = 300) -> list[dict]:
    """Probas publiques agrégées (Polymarket par volume + Kalshi). [] si réseau KO."""
    poly = _parse_polymarket(_get_json(_POLY_URL.format(limit=limit)))
    kalshi = _parse_kalshi(_get_json(_KALSHI_URL.format(limit=limit)))
    return poly + kalshi


def implied_probability(records: list[dict], keyword: str) -> float | None:
    """Proba du 1er marché contenant `keyword` (insensible casse). None si absent."""
    kw = keyword.lower()
    for r in records:
        if kw in str(r.get("question", "")).lower():
            return r.get("probability")
    return None


def signals_for(records: list[dict], keyword_map: dict[str, list[str]]) -> dict:
    """{label: proba} — 1er marché contenant l'un des mots-clés du label."""
    out: dict[str, float | None] = {}
    for label, kws in keyword_map.items():
        kws_l = [k.lower() for k in kws]
        prob = None
        for r in records:
            q = str(r.get("question", "")).lower()
            if any(k in q for k in kws_l):
                prob = r.get("probability")
                break
        out[label] = prob
    return out


def macro_signals(records: list[dict] | None = None, limit: int = 300) -> dict:
    """Probas MACRO (Fed, CPI, récession, emploi, shutdown). Forward-looking."""
    recs = records if records is not None else fetch_markets(limit)
    return signals_for(recs, MACRO_KEYWORDS)


def asset_signals(tickers: list[str], records: list[dict] | None = None,
                  names: dict[str, str] | None = None, limit: int = 300) -> dict:
    """Probas sur marchés mentionnant un actif (ticker/nom/crypto). {ticker: proba}."""
    recs = records if records is not None else fetch_markets(limit)
    name_map = {**_CRYPTO_NAMES, **(names or {})}
    km = {tk: [tk, name_map.get(tk.upper(), tk)] for tk in tickers}
    return signals_for(recs, km)


def earnings_signals(tickers: list[str], records: list[dict] | None = None,
                     names: dict[str, str] | None = None, limit: int = 300) -> dict:
    """Probas RÉSULTATS sociétés (question = earnings/beat/revenue ET l'actif)."""
    recs = records if records is not None else fetch_markets(limit)
    name_map = names or {}
    terms = ("earnings", "beat", "revenue", "guidance")
    out: dict[str, float | None] = {}
    for tk in tickers:
        needles = {tk.lower(), name_map.get(tk.upper(), tk).lower()}
        prob = None
        for r in recs:
            q = str(r.get("question", "")).lower()
            if any(t in q for t in terms) and any(n in q for n in needles):
                prob = r.get("probability")
                break
        out[tk] = prob
    return out
