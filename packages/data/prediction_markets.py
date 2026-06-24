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


MAX_SPREAD = 0.15   # carnet plus large que 15 pts = illiquide → bruit (filtre Jobs)
DEBIAS_ALPHA = 1.15  # >1 corrige le biais favori-outsider (recalibration power)


def _get_json(url: str, timeout: float = 6.0) -> Any:
    """GET JSON best-effort (stdlib). None sur toute erreur (réseau, parse, timeout)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-terminal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URLs publiques fixes
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - best-effort, jamais bloquant
        return None


def _num(x: Any) -> float | None:
    """float(x) tolérant. None si non convertible (champ absent/vide)."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def debias(p: float, alpha: float = DEBIAS_ALPHA) -> float:
    """Corrige le biais favori-outsider (recalibration *power*).

    Les outsiders (p faible) sont structurellement sur-pricés et les favoris (p
    élevé) sous-pricés : `p**a / (p**a + (1-p)**a)` avec a>1 repousse vers les
    extrêmes → proba « vraie » plus honnête. a=1 → identité. Effet volontaire-
    ment modéré (la foule reste un overlay de risque, pas un signal d'alpha).
    """
    q = min(max(float(p), 1e-4), 1 - 1e-4)
    return round(q**alpha / (q**alpha + (1 - q) ** alpha), 4)


def _parse_polymarket(data: Any) -> list[dict]:
    """Gamma Polymarket → [{source, question, probability, spread, volume, end}]."""
    out: list[dict] = []
    for m in data or []:
        prices = m.get("outcomePrices")
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except json.JSONDecodeError:
                prices = None
        last = _num(prices[0]) if isinstance(prices, list) and prices else None
        bid, ask = _num(m.get("bestBid")), _num(m.get("bestAsk"))
        mid = (bid + ask) / 2 if bid is not None and ask is not None else last
        spread = _num(m.get("spread"))
        if spread is None and bid is not None and ask is not None:
            spread = abs(ask - bid)
        vol = _num(m.get("volume24hr")) or _num(m.get("volume"))
        q = m.get("question") or m.get("title")
        if q and mid is not None:
            out.append({"source": "polymarket", "question": q,
                        "probability": round(mid, 4),
                        "spread": round(spread, 4) if spread is not None else None,
                        "volume": vol, "end": m.get("endDate")})
    return out


def _parse_kalshi(data: Any) -> list[dict]:
    """Kalshi → [{source, question, probability, spread, volume, end}] (cents)."""
    out: list[dict] = []
    for m in (data or {}).get("markets", []):
        bid, ask = _num(m.get("yes_bid")), _num(m.get("yes_ask"))
        last = _num(m.get("last_price"))
        if bid is not None and ask is not None:
            mid, spread = (bid + ask) / 2 / 100.0, abs(ask - bid) / 100.0
        else:
            price = last if last is not None else bid
            mid = price / 100.0 if price is not None else None
            spread = None
        vol = _num(m.get("volume")) or _num(m.get("open_interest"))
        q = m.get("title") or m.get("ticker")
        if q and mid is not None:
            out.append({"source": "kalshi", "question": q,
                        "probability": round(mid, 4),
                        "spread": round(spread, 4) if spread is not None else None,
                        "volume": vol, "end": m.get("close_time")})
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


def signals_detail(records: list[dict], keyword_map: dict[str, list[str]],
                   alpha: float = DEBIAS_ALPHA,
                   max_spread: float = MAX_SPREAD) -> dict:
    """{label: {p, p_adj, spread, volume, source}} — 1er marché LIQUIDE par label.

    Comme `signals_for` mais renvoie le détail microstructure + la proba dé-biaisée,
    et IGNORE les carnets trop larges (`spread > max_spread`) = filtre anti-bruit.
    """
    out: dict[str, dict | None] = {}
    for label, kws in keyword_map.items():
        kws_l = [k.lower() for k in kws]
        hit = None
        for r in records:
            sp = r.get("spread")
            if sp is not None and sp > max_spread:
                continue                                  # illiquide → on saute
            if any(k in str(r.get("question", "")).lower() for k in kws_l):
                hit = r
                break
        if hit is None:
            out[label] = None
            continue
        p = hit.get("probability")
        out[label] = {"p": p, "p_adj": debias(p, alpha) if p is not None else None,
                      "spread": hit.get("spread"), "volume": hit.get("volume"),
                      "source": hit.get("source")}
    return out


def macro_signals(records: list[dict] | None = None, limit: int = 300) -> dict:
    """Probas MACRO (Fed, CPI, récession, emploi, shutdown). Forward-looking."""
    recs = records if records is not None else fetch_markets(limit)
    return signals_for(recs, MACRO_KEYWORDS)


def macro_detail(records: list[dict] | None = None, alpha: float = DEBIAS_ALPHA,
                 limit: int = 300) -> dict:
    """Détail microstructure + proba dé-biaisée des marchés MACRO (non-None)."""
    recs = records if records is not None else fetch_markets(limit)
    return {k: v for k, v in signals_detail(recs, MACRO_KEYWORDS, alpha).items()
            if v is not None}


def asset_detail(tickers: list[str], records: list[dict] | None = None,
                 names: dict[str, str] | None = None, alpha: float = DEBIAS_ALPHA,
                 limit: int = 300) -> dict:
    """Détail microstructure + proba dé-biaisée par actif (ticker/nom/crypto)."""
    recs = records if records is not None else fetch_markets(limit)
    name_map = {**_CRYPTO_NAMES, **(names or {})}
    km = {tk: [tk, name_map.get(tk.upper(), tk)] for tk in tickers}
    return {k: v for k, v in signals_detail(recs, km, alpha).items() if v is not None}


def earnings_detail(tickers: list[str], records: list[dict] | None = None,
                    names: dict[str, str] | None = None, alpha: float = DEBIAS_ALPHA,
                    limit: int = 300) -> dict:
    """Proba RÉSULTATS dé-biaisée par société {ticker: {p, p_adj}} (non-None)."""
    recs = records if records is not None else fetch_markets(limit)
    base = earnings_signals(tickers, records=recs, names=names)
    return {tk: {"p": p, "p_adj": debias(p, alpha)}
            for tk, p in base.items() if p is not None}


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
