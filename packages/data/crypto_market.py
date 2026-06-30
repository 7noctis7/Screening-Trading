"""Cockpit crypto — données marché agrégées (gratuit, sans clé). Build-time + client.

Sources publiques CORS-friendly : CoinGecko (global, markets, categories, trending),
DefiLlama (chains TVL, stablecoins), alternative.me (Fear & Greed). Best-effort : chaque
section None/[] si la source tombe (jamais de chiffre inventé). Parsers purs,
séparés du réseau (testables hors-ligne, réutilisables côté client).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
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
_BLOCKCOUNT = "https://blockchain.info/q/getblockcount"   # hauteur de bloc BTC (entier)

_STABLE_SYMS = {"USDT", "USDC", "DAI", "USDE", "USDS", "USD1", "FDUSD", "TUSD",
                "PYUSD", "USDD", "FRAX", "GUSD", "LUSD", "USDP", "BUSD"}


_CACHE_DIR = Path(os.environ.get("QUANT_CACHE_DIR", ".cache/crypto"))


def _cache_path(url: str) -> Path:
    return _CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".json")  # noqa: S324


def _cache_read(url: str) -> Any:
    """Dernière réponse valide connue (anti rate-limit). None si absente/illisible."""
    p = _cache_path(url)
    try:
        return json.loads(p.read_text("utf-8")) if p.exists() else None
    except Exception:  # noqa: BLE001
        return None


def _cache_write(url: str, data: Any) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(url).write_text(json.dumps(data), "utf-8")
    except OSError:
        pass


def _get_json(url: str, timeout: float = 10.0, retries: int | None = None) -> Any:
    """GET JSON robuste : retries + backoff, puis repli sur le cache disque.

    Best-effort souverain : si la source rate-limit/tombe, on RÉUTILISE la dernière
    réponse valide (cache) plutôt que d'afficher du vide — jamais de chiffre inventé.
    Tunable par env : QUANT_HTTP_RETRIES (déf. 3), QUANT_HTTP_BACKOFF (déf. 1.5 s ;
    0 = pas d'attente, utile en tests hors-ligne).
    """
    if retries is None:
        retries = int(os.environ.get("QUANT_HTTP_RETRIES", "3"))
    backoff = float(os.environ.get("QUANT_HTTP_BACKOFF", "1.5"))
    for attempt in range(max(1, retries)):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "quant-terminal/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
                data = json.loads(r.read().decode("utf-8"))
            _cache_write(url, data)
            return data
        except Exception:  # noqa: BLE001
            if attempt < retries - 1 and backoff > 0:
                time.sleep(backoff * (attempt + 1))
    return _cache_read(url)                                # repli : dernière donnée OK


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
    """stablecoins.llama.fi → [{sym, mcap, price, peg_dev, kind}].

    `kind` distingue les vrais pegs $1 des tokens À RENDEMENT (NAV qui dérive
    structurellement, ex. USYC ~1,13 $) : les flagger « décrochés » serait trompeur.
    """
    out = []
    for s in ((data or {}).get("peggedAssets") or []):
        circ = (s.get("circulating") or {}).get("peggedUSD")
        mcap = _num(circ)
        price = _num(s.get("price"))
        if s.get("symbol") and mcap:
            peg = round(price - 1.0, 4) if price is not None else None
            # NAV structurellement loin de 1 $ → token à rendement, pas un dépeg.
            kind = ("yield" if price is not None and (price >= 1.05 or price <= 0.5)
                    else "peg")
            out.append({"sym": s["symbol"], "mcap": mcap, "price": price,
                        "peg_dev": peg, "kind": kind})
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


def _ret7d(spark: Any) -> float | None:
    """Rendement 7 j depuis le sparkline (dernier/premier − 1). None si indispo."""
    if not spark or len(spark) < 2:
        return None
    a, b = spark[0], spark[-1]
    return (b / a - 1.0) if a else None


def altseason(markets: list[dict], top: int = 50) -> dict:
    """Part du top `top` (hors stablecoins) battant BTC sur 7 j → proxy altseason.

    Dérivé des sparklines DÉJÀ récupérés (aucun appel réseau, aucun chiffre inventé).
    ≥75 % battent BTC = « Altseason » ; ≤25 % = « Bitcoin » ; sinon « Mixte ».
    """
    btc = next((m for m in markets if m.get("sym") == "BTC"), None)
    btc_r = _ret7d(btc.get("spark7d")) if btc else None
    if btc_r is None:
        return {"available": False}
    valid = [m for m in markets if m.get("mcap") and m.get("sym") not in _STABLE_SYMS]
    valid.sort(key=lambda m: m["mcap"], reverse=True)
    rets = [r for m in valid[:top] if m.get("sym") != "BTC"
            and (r := _ret7d(m.get("spark7d"))) is not None]
    if len(rets) < 10:
        return {"available": False}
    beat = sum(1 for r in rets if r > btc_r)
    pct = round(100 * beat / len(rets), 1)
    label = "Altseason" if pct >= 75 else "Bitcoin" if pct <= 25 else "Mixte"
    return {"available": True, "pct": pct, "n": len(rets),
            "btc_ret7d": round(btc_r, 4), "label": label}


def halving(height: Any) -> dict:
    """Compte à rebours du halving BTC depuis la hauteur de bloc RÉELLE.

    Halving tous les 210 000 blocs ; ~10 min/bloc. Aucune date inventée : on rend
    `blocks_left` (exact) et `days_left` (estimation explicite à ~10 min/bloc).
    """
    if not isinstance(height, (int, float)) or height <= 0:
        return {"available": False}
    height = int(height)
    interval = 210_000
    nxt = (height // interval + 1) * interval
    left = nxt - height
    return {"available": True, "height": height, "halving_block": nxt,
            "blocks_left": left, "days_left": round(left * 10 / 1440),
            "number": nxt // interval,
            "progress": round((interval - left) / interval, 4)}


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def accumulation_score(ck: dict) -> dict:
    """Score d'Accumulation Institutionnelle 0-100 — CONTRARIAN, déterministe.

    Haut = conditions d'accumulation (peur, shorts surchauffés, poudre sèche élevée) ;
    bas = euphorie/distribution. Pondère 3 signaux issus du cockpit (aucun inventé) :
    peur (F&G), funding négatif (dérivés), part stablecoins (capital prêt à entrer).
    """
    parts: list[tuple[float, float]] = []          # (poids, signal 0-1)
    drivers: list[str] = []
    fng = ck.get("fng") or {}
    if fng.get("available") and fng.get("value") is not None:
        s = (100.0 - float(fng["value"])) / 100.0   # peur ↑ → accumulation ↑
        parts.append((0.40, s))
        drivers.append(f"peur (F&G {fng['value']:.0f})")
    se = (ck.get("derivatives") or {}).get("sentiment") or {}
    if se.get("available") and se.get("avg") is not None:
        s = _clip(-se["avg"] / 0.0005)              # funding négatif → accumulation
        parts.append((0.35, s))
        drivers.append(f"funding {se['avg'] * 100:+.3f}%/8h")
    g = ck.get("global") or {}
    tot = g.get("total_mcap")
    stab = sum(x["mcap"] for x in (ck.get("stablecoins") or []) if x.get("mcap"))
    if tot and stab:
        share = stab / tot
        parts.append((0.25, _clip(share / 0.12)))   # part stable ↑ → poudre sèche ↑
        drivers.append(f"poudre sèche {share * 100:.1f}% (stablecoins)")
    if not parts:
        return {"available": False}
    wsum = sum(w for w, _ in parts)
    score = round(sum(w * v for w, v in parts) / wsum * 100, 1)
    label = ("🟢 ACCUMULATION" if score >= 60
             else "🔴 EUPHORIE" if score <= 40 else "🟡 NEUTRE")
    return {"available": True, "score": score, "label": label, "drivers": drivers}


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
    ck["altseason"] = altseason(markets)
    ck["halving"] = halving(_get_json(_BLOCKCOUNT))
    ck["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    return ck
