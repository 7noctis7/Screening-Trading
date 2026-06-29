"""Dérivés crypto — normalisation multi-CEX (pattern Coinglass/Velodata, build-time).

Chaque CEX expose un schéma RADICALEMENT différent ; on normalise vers un événement
CANONIQUE unique, puis on réduit en signaux (funding agrégé, sentiment de liquidation).
Parsers/adaptateurs PURS (testables hors-ligne) ; réseau best-effort + cache via
crypto_market._get_json. Jamais de chiffre inventé : section vide si la source tombe.

Funding (perp) : positif = longs paient shorts = longs surchauffés (biais contrarian
baissier) ; négatif = shorts surchauffés (biais haussier). 3 règlements/j → annualisé
≈ rate × 3 × 365.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.data.crypto_market import _get_json, _num

_BYBIT = "https://api.bybit.com/v5/market/tickers?category=linear&symbol={s}USDT"
_OKX = "https://www.okx.com/api/v5/public/funding-rate?instId={s}-USD-SWAP"
_BINANCE = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol={s}USDT"


# ---- Funding : adaptateurs PURS (schéma hétérogène → rate flottant) ----
def from_bybit_ticker(data) -> float | None:
    row = (((data or {}).get("result") or {}).get("list") or [{}])
    return _num(row[0].get("fundingRate")) if row else None


def from_okx(data) -> float | None:
    row = ((data or {}).get("data") or [{}])
    return _num(row[0].get("fundingRate")) if row else None


def from_binance_premium(data) -> float | None:
    return _num((data or {}).get("lastFundingRate"))


def aggregate_funding(venues: dict[str, float | None]) -> dict:
    """{exchange: rate} → moyenne inter-venues + annualisé. None ignorés."""
    vals = [v for v in venues.values() if v is not None]
    if not vals:
        return {"available": False, "venues": venues}
    mean = sum(vals) / len(vals)
    return {"available": True, "venues": venues, "mean": round(mean, 6),
            "annualized": round(mean * 3 * 365, 4), "n_venues": len(vals)}


def funding_sentiment(rows: list[dict], hi: float = 0.0003) -> dict:
    """Sentiment depuis le funding moyen des majors (seuil ≈ 0,03 %/8h)."""
    means = [r["mean"] for r in rows if r.get("available")]
    if not means:
        return {"available": False}
    avg = sum(means) / len(means)
    label = ("longs surchauffés (contrarian baissier)" if avg > hi
             else "shorts surchauffés (contrarian haussier)" if avg < -hi
             else "levier équilibré")
    return {"available": True, "avg": round(avg, 6),
            "annualized": round(avg * 3 * 365, 4), "label": label}


def derivatives(symbols: tuple[str, ...] = ("BTC", "ETH", "SOL")) -> dict:
    """Funding actuel normalisé multi-CEX + sentiment. Best-effort, sans clé."""
    rows: list[dict] = []
    for s in symbols:
        venues = {
            "bybit": from_bybit_ticker(_get_json(_BYBIT.format(s=s))),
            "okx": from_okx(_get_json(_OKX.format(s=s))),
            "binance": from_binance_premium(_get_json(_BINANCE.format(s=s))),
        }
        agg = aggregate_funding(venues)
        if agg.get("available"):
            rows.append({"symbol": s, **agg})
    if not rows:
        return {"available": False}
    return {"available": True, "rows": rows, "sentiment": funding_sentiment(rows)}


# ---- Liquidations : événement CANONIQUE + adaptateurs + sentiment temps réel ----
# (pattern flux WS Coinglass/Velodata ; lib pure prête pour un worker streaming —
#  non câblée au build statique car les liquidations sont WS-only, pas REST.)
@dataclass(frozen=True)
class Liq:
    ts: int
    exchange: str
    symbol: str
    side: str        # "long" = un LONG a été liquidé ; "short" = un SHORT liquidé
    usd: float


def liq_from_binance(r: dict) -> Liq:
    o = r["o"]                                            # !forceOrder@arr
    return Liq(int(o["T"]), "binance", o["s"],
               "long" if o["S"] == "SELL" else "short",
               float(o["q"]) * float(o["ap"]))


def liq_from_bybit(r: dict) -> Liq:
    d = r["data"]                                         # topic "liquidation"
    return Liq(int(r["ts"]), "bybit", d["symbol"],
               "long" if d["side"] == "Sell" else "short",
               float(d["size"]) * float(d["price"]))


def liquidation_sentiment(events: list[Liq]) -> dict:
    """Déséquilibre long/short pondéré notionnel ∈ [-1, +1].

    >0 = cascade de SHORTS liquidés (squeeze haussier) ; <0 = LONGS balayés
    (capitulation). Réduction d'un flux d'événements canoniques en un score.
    """
    longs = sum(e.usd for e in events if e.side == "long")
    shorts = sum(e.usd for e in events if e.side == "short")
    tot = longs + shorts
    if tot <= 0:
        return {"available": False}
    score = round((shorts - longs) / tot, 3)
    label = ("squeeze haussier" if score > 0.33
             else "capitulation longs" if score < -0.33 else "équilibré")
    return {"available": True, "score": score, "label": label,
            "long_usd": longs, "short_usd": shorts, "n": len(events)}
