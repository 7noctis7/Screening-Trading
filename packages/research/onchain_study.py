"""Étude alt-data ON-CHAIN — le ratio TVL/MCap prédit-il les rendements crypto ?

Thèse : un token dont la cap est ADOSSÉE à une forte activité on-chain (TVL/MCap élevé)
serait « moins cher » → sur-performance ; et inversement. On teste honnêtement via le
MÊME gate que le reste : event-study cross-actif sur le z-score causal du facteur +
placebo. Historique gratuit/sans-clé (CoinGecko market_chart + DefiLlama historique).

Réutilise `funding_study` (z causal + significativité poolée). Verdict via le placebo :
l'effet bat-il le hasard ? Échantillon mince (peu de cryptos avec TVL, historique court)
→ probable négatif propre, mais traçable. Parsers séparés du réseau → testables.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from packages.data.crypto_onchain import COINS

_CG_CHART = ("https://api.coingecko.com/api/v3/coins/{id}/market_chart"
             "?vs_currency=usd&days={days}&interval=daily")
_LLAMA_CHAIN_HIST = "https://api.llama.fi/v2/historicalChainTvl/{chain}"
_LLAMA_PROTO = "https://api.llama.fi/protocol/{slug}"
_LLAMA_FEES_CHAIN = ("https://api.llama.fi/overview/fees/{chain}"
                     "?excludeTotalDataChartBreakdown=true")
_LLAMA_FEES_PROTO = "https://api.llama.fi/summary/fees/{slug}?dataType=dailyFees"

# Facteurs on-chain testables (numérateur / market cap). Chacun passe par le gate.
FACTORS = ("tvl_mcap", "fees_mcap")


def _get_json(url: str, timeout: float = 10.0) -> Any:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-terminal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _day(ts_ms_or_s: float) -> str:
    from datetime import UTC, datetime
    ts = ts_ms_or_s / 1000 if ts_ms_or_s > 1e11 else ts_ms_or_s
    return datetime.fromtimestamp(ts, UTC).date().isoformat()


def parse_cg_chart(data: Any) -> dict[str, dict]:
    """market_chart → {jour: {price, mcap}} (1 point/jour)."""
    out: dict[str, dict] = {}
    prices = (data or {}).get("prices") or []
    caps = {(_day(t)): v for t, v in ((data or {}).get("market_caps") or [])}
    for t, p in prices:
        d = _day(t)
        out[d] = {"price": float(p), "mcap": caps.get(d)}
    return out


def parse_llama_hist(data: Any) -> dict[str, float]:
    """historicalChainTvl → {jour: tvl}."""
    out: dict[str, float] = {}
    for row in data or []:
        d, tvl = row.get("date"), row.get("tvl")
        if d is not None and tvl is not None:
            out[_day(float(d))] = float(tvl)
    return out


def parse_llama_proto(data: Any) -> dict[str, float]:
    """/protocol/{slug} → {jour: tvl} (série totalLiquidityUSD)."""
    out: dict[str, float] = {}
    for row in ((data or {}).get("tvl") or []):
        d, tvl = row.get("date"), row.get("totalLiquidityUSD")
        if d is not None and tvl is not None:
            out[_day(float(d))] = float(tvl)
    return out


def parse_llama_fees(data: Any) -> dict[str, float]:
    """overview/summary fees → {jour: fees} (série totalDataChart [[ts, val]])."""
    out: dict[str, float] = {}
    for row in ((data or {}).get("totalDataChart") or []):
        if isinstance(row, list) and len(row) == 2 and row[1] is not None:
            out[_day(float(row[0]))] = float(row[1])
    return out


def _tvl_hist(sym: str) -> dict[str, float]:
    meta = COINS.get(sym, {})
    if "chain" in meta:
        u = _LLAMA_CHAIN_HIST.format(chain=meta["chain"])
        return parse_llama_hist(_get_json(u))
    if "proto" in meta:
        return parse_llama_proto(_get_json(_LLAMA_PROTO.format(slug=meta["proto"])))
    return {}


def _fees_hist(sym: str) -> dict[str, float]:
    meta = COINS.get(sym, {})
    if "chain" in meta:
        # l'endpoint fees attend un slug MINUSCULE (≠ le nom capitalisé du TVL).
        u = _LLAMA_FEES_CHAIN.format(chain=meta["chain"].lower())
        return parse_llama_fees(_get_json(u))
    if "proto" in meta:
        u = _LLAMA_FEES_PROTO.format(slug=meta["proto"])
        return parse_llama_fees(_get_json(u))
    return {}


def _numerator_hist(sym: str, factor: str) -> dict[str, float]:
    return _fees_hist(sym) if factor == "fees_mcap" else _tvl_hist(sym)


def coin_series(sym: str, factor: str = "tvl_mcap", days: int = 365):
    """(rendements, z causal de `factor`/MCap) alignés par jour. None si insuffisant."""
    import numpy as np

    from packages.research.funding_study import zscore_causal
    meta = COINS.get(sym)
    if not meta:
        return None
    chart = parse_cg_chart(_get_json(_CG_CHART.format(id=meta["cg"], days=days)))
    num = _numerator_hist(sym, factor)
    common = sorted(set(chart) & set(num))
    rows = [(d, chart[d]["price"], chart[d]["mcap"], num[d]) for d in common
            if chart[d].get("mcap")]
    if len(rows) < 60:
        return None
    closes = np.array([r[1] for r in rows], float)
    rets = closes[1:] / closes[:-1] - 1.0
    fac = np.array([r[3] / r[2] for r in rows], float)[1:]     # facteur/MCap, aligné
    return rets, zscore_causal(fac, 30)


def run_study(symbols: list[str] | None = None, factor: str = "tvl_mcap",
              post: int = 5, threshold: float = 1.5) -> dict:
    """Event-study cross-actif d'un facteur on-chain (placebo). Via funding_study."""
    from packages.research.funding_study import aggregate_significance
    series = {}
    for s in (symbols or list(COINS)):
        v = coin_series(s, factor)
        if v:
            series[s] = v
    if len(series) < 2:
        return {"available": False, "n_assets": len(series)}
    return aggregate_significance(series, post=post, threshold=threshold,
                                  n_sims=1000, seed=7)
