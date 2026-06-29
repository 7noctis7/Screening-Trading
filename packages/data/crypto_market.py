"""Cockpit crypto — données marché agrégées (gratuit, sans clé). Build-time + client.

Sources publiques CORS-friendly : CoinGecko (global, markets, categories, trending),
DefiLlama (chains TVL, stablecoins), alternative.me (Fear & Greed). Best-effort : chaque
section None/[] si la source tombe (jamais de chiffre inventé). Parsers purs,
séparés du réseau (testables hors-ligne, réutilisables côté client).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

_CG = "https://api.coingecko.com/api/v3"
_GLOBAL = _CG + "/global"
_MARKETS = (_CG + "/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100"
            "&page=1&sparkline=true&price_change_percentage=24h")
_CATEGORIES = _CG + "/coins/categories"
_TRENDING = _CG + "/search/trending"
_LLAMA_CHAINS = "https://api.llama.fi/v2/chains"
_STABLES = "https://stablecoins.llama.fi/stablecoins?includePrices=true"
_FNG = "https://api.alternative.me/fng/?limit=1"


def _get_json(url: str, timeout: float = 10.0) -> Any:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-terminal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _num(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_global(data: Any) -> dict:
    """/global → cap totale, dominance BTC/ETH, variation cap 24 h."""
    d = (data or {}).get("data") or {}
    mc = d.get("total_market_cap") or {}
    dom = d.get("market_cap_percentage") or {}
    return {"total_mcap": _num(mc.get("usd")),
            "btc_dom": _num(dom.get("btc")), "eth_dom": _num(dom.get("eth")),
            "mcap_chg_24h": _num(d.get("market_cap_change_percentage_24h_usd"))}


def parse_markets(data: Any) -> list[dict]:
    """/coins/markets → [{id, sym, name, price, chg24h, mcap, spark7d}]."""
    out: list[dict] = []
    for m in data or []:
        spark = ((m.get("sparkline_in_7d") or {}).get("price")) or []
        out.append({
            "id": m.get("id"), "sym": str(m.get("symbol") or "").upper(),
            "name": m.get("name"), "price": _num(m.get("current_price")),
            "chg24h": _num(m.get("price_change_percentage_24h")),
            "mcap": _num(m.get("market_cap")),
            "spark7d": [float(x) for x in spark[-48:] if x is not None],
        })
    return out


def movers(markets: list[dict], n: int = 8) -> dict:
    """Top gagnants / perdants 24 h depuis les markets (top 100 cap)."""
    valid = [m for m in markets if m.get("chg24h") is not None]
    s = sorted(valid, key=lambda m: m["chg24h"])
    return {"losers": s[:n], "gainers": list(reversed(s[-n:]))}


def parse_categories(data: Any, n: int = 10) -> list[dict]:
    """/coins/categories → narratifs triés par perf 24 h [{id, name, chg24h, mcap}]."""
    out = []
    for c in data or []:
        chg = _num(c.get("market_cap_change_24h"))
        if c.get("name") and chg is not None:
            out.append({"id": c.get("id"), "name": c["name"], "chg24h": chg,
                        "mcap": _num(c.get("market_cap"))})
    out.sort(key=lambda x: x["chg24h"], reverse=True)
    return out[:n]


def parse_trending(data: Any) -> list[dict]:
    """/search/trending → [{id, name, sym, rank}]."""
    out = []
    for c in ((data or {}).get("coins") or []):
        it = c.get("item") or {}
        if it.get("name"):
            out.append({"id": it.get("id"), "name": it["name"],
                        "sym": str(it.get("symbol") or "").upper(),
                        "rank": it.get("market_cap_rank")})
    return out


def parse_chains(data: Any, n: int = 8) -> dict:
    """/v2/chains → TVL DeFi totale + top chaînes + dominance %."""
    rows = [{"chain": c.get("name"), "tvl": _num(c.get("tvl"))}
            for c in (data or []) if c.get("name") and _num(c.get("tvl"))]
    total = sum(r["tvl"] for r in rows) or 0.0
    rows.sort(key=lambda r: r["tvl"], reverse=True)
    top = [{**r, "dom": round(r["tvl"] / total, 4) if total else None}
           for r in rows[:n]]
    return {"total_tvl": total or None, "top": top}


def parse_stablecoins(data: Any, n: int = 8) -> list[dict]:
    """stablecoins.llama.fi → [{sym, mcap, price, peg_dev}] (écart au peg $1)."""
    out = []
    for s in ((data or {}).get("peggedAssets") or []):
        circ = (s.get("circulating") or {}).get("peggedUSD")
        mcap = _num(circ)
        price = _num(s.get("price"))
        if s.get("symbol") and mcap:
            peg = round(price - 1.0, 4) if price is not None else None
            out.append({"sym": s["symbol"], "mcap": mcap, "price": price,
                        "peg_dev": peg})
    out.sort(key=lambda x: x["mcap"], reverse=True)
    return out[:n]


def parse_fng(data: Any) -> dict:
    """alternative.me /fng → {value 0-100, label}."""
    arr = (data or {}).get("data") or []
    if not arr:
        return {"available": False}
    v = _num(arr[0].get("value"))
    return {"available": v is not None, "value": v,
            "label": arr[0].get("value_classification")}


def market_sentiment(ck: dict) -> dict:
    """Sentiment marché DÉTERMINISTE depuis le cockpit (F&G + cap 24 h + breadth).

    Aucun chiffre inventé : score = moyenne des signaux disponibles, label dérivé.
    Renvoie {label, score 0-100, drivers}. None-safe (sources manquantes ignorées).
    """
    signals: list[float] = []
    drivers: list[str] = []
    fng = ck.get("fng") or {}
    if fng.get("available") and fng.get("value") is not None:
        signals.append(float(fng["value"]))
        drivers.append(f"Fear & Greed {fng['value']:.0f} ({fng.get('label') or '—'})")
    g = ck.get("global") or {}
    chg = g.get("mcap_chg_24h")
    if chg is not None:
        signals.append(max(0.0, min(100.0, 50.0 + chg * 5.0)))
        drivers.append(f"capitalisation 24 h {chg:+.1f}%")
    gain = ck.get("gainers") or []
    lose = ck.get("losers") or []
    up = sum(1 for m in (gain + lose) if (m.get("chg24h") or 0) > 0)
    tot = len(gain) + len(lose)
    if tot:
        breadth = up / tot
        signals.append(breadth * 100.0)
        drivers.append(f"breadth {up}/{tot} en hausse")
    if not signals:
        return {"available": False}
    score = sum(signals) / len(signals)
    label = "BULLISH" if score >= 60 else "BEARISH" if score <= 40 else "NEUTRE"
    return {"available": True, "label": label, "score": round(score, 1),
            "drivers": drivers}


def cockpit() -> dict:
    """Assemble le cockpit (build-time). Chaque section best-effort (None/[] si KO)."""
    markets = parse_markets(_get_json(_MARKETS))
    mv = movers(markets)
    ck = {
        "global": parse_global(_get_json(_GLOBAL)),
        "top": [m for m in markets if m["sym"] in ("BTC", "ETH", "SOL")],
        "gainers": mv["gainers"], "losers": mv["losers"],
        "categories": parse_categories(_get_json(_CATEGORIES)),
        "trending": parse_trending(_get_json(_TRENDING)),
        "defi": parse_chains(_get_json(_LLAMA_CHAINS)),
        "stablecoins": parse_stablecoins(_get_json(_STABLES)),
        "fng": parse_fng(_get_json(_FNG)),
    }
    ck["sentiment"] = market_sentiment(ck)
    return ck
