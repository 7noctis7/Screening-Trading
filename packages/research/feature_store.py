"""Feature store point-in-time — jointure AS-OF (anti look-ahead par construction).

Pour chaque event, on attache le prix CONNU à `ts_public` (dernier close ≤ ts_public).
Aucun prix futur ne peut entrer → zéro skew (Ghodsi). Pur Python (bisect). À l'échelle :
DuckDB `ASOF JOIN ... ON p.ts <= e.ts_public` (même sémantique).
"""

from __future__ import annotations

from bisect import bisect_right


def asof_price(price_series: list[tuple[str, float]], ts_public: str) -> float | None:
    """Dernier close ≤ ts_public. `price_series` = liste TRIÉE de (ts_iso, close)."""
    if not price_series:
        return None
    ts = [p[0] for p in price_series]
    i = bisect_right(ts, ts_public)
    return price_series[i - 1][1] if i > 0 else None


def asof_join(events: list[dict],
              prices_by_ticker: dict[str, list[tuple[str, float]]]) -> list[dict]:
    """Jointure as-of : 1 ligne par (event, ticker) avec le close connu à `ts_public`.

    `asof_close = None` si aucun prix antérieur (event avant l'historique) → exclu du
    feature set en aval (jamais comblé par un prix futur).
    """
    rows: list[dict] = []
    for e in events:
        for tk in e.get("tickers", []):
            close = asof_price(prices_by_ticker.get(tk, []), e["ts_public"])
            rows.append({
                "hash": e.get("hash"), "ts_public": e["ts_public"],
                "type": e.get("type"), "ticker": tk, "asof_close": close,
            })
    return rows
