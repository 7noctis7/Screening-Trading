"""Fondamentaux on-chain crypto — multi-sources GRATUITES, sans clé (par défaut).

Couvre des actifs hétérogènes (L1 PoW/PoS, app-chain, tokens) avec ce qui existe
en gratuit/sans-clé :
- CoinGecko  : mcap, volume, supply/float, DD-ATH, momentum (flow) — TOUS les actifs.
- DefiLlama  : TVL (proxy d'activité on-chain) — chains (ETH/SOL/NEAR/HYPE) &
               protocoles (ONDO/LINK).
- (BTC)      : hash rate via mempool.space (PoW) — optionnel.
- Etherscan  : OPT-IN si ETHERSCAN_API_KEY (ERC-20 LINK/ONDO) — jamais requis.

Métriques dérivées exploitables : turnover (vol/mcap), float_ratio (circ/max → overhang
d'unlocks), tvl_mcap (proxy NVT/valorisation), dd_ath, momentum. Best-effort (None si
indispo). Parsers SÉPARÉS du réseau → testables hors-ligne. Aucune clé ⇒ aucun secret.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

# symbole → (id CoinGecko, chaîne DefiLlama, protocole DefiLlama)
COINS: dict[str, dict[str, str]] = {
    "BTC": {"cg": "bitcoin"},
    "ETH": {"cg": "ethereum", "chain": "Ethereum"},
    "SOL": {"cg": "solana", "chain": "Solana"},
    "NEAR": {"cg": "near", "chain": "Near"},
    "HYPE": {"cg": "hyperliquid", "chain": "Hyperliquid"},
    "ONDO": {"cg": "ondo-finance", "proto": "ondo-finance"},
    "LINK": {"cg": "chainlink", "proto": "chainlink"},
    "RENDER": {"cg": "render-token"},
}
_CG = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids}"
       "&price_change_percentage=7d,30d")
_LLAMA_CHAINS = "https://api.llama.fi/v2/chains"
_LLAMA_TVL = "https://api.llama.fi/tvl/{slug}"


def _get_json(url: str, timeout: float = 8.0) -> Any:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-terminal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - best-effort
        return None


def _num(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_coingecko(data: Any) -> dict[str, dict]:
    """Liste /coins/markets → {cg_id: {mcap, vol, circ, maxs, ath_chg, chg7d/30d}}."""
    out: dict[str, dict] = {}
    for m in data or []:
        cid = m.get("id")
        if not cid:
            continue
        out[cid] = {
            "mcap": _num(m.get("market_cap")),
            "vol": _num(m.get("total_volume")),
            "circ": _num(m.get("circulating_supply")),
            "maxs": _num(m.get("max_supply")) or _num(m.get("total_supply")),
            "ath_chg": _num(m.get("ath_change_percentage")),
            "chg7d": _num(m.get("price_change_percentage_7d_in_currency")),
            "chg30d": _num(m.get("price_change_percentage_30d_in_currency")),
        }
    return out


def parse_llama_chains(data: Any) -> dict[str, float]:
    """/v2/chains → {nom_chaîne_minuscule: tvl}."""
    out: dict[str, float] = {}
    for c in data or []:
        name, tvl = c.get("name"), _num(c.get("tvl"))
        if name and tvl is not None:
            out[str(name).lower()] = tvl
    return out


def derive(cg: dict | None, tvl: float | None) -> dict:
    """Métriques dérivées exploitables à partir du flow CoinGecko + TVL."""
    cg = cg or {}
    mcap, vol = cg.get("mcap"), cg.get("vol")
    circ, maxs = cg.get("circ"), cg.get("maxs")
    return {
        "mcap": mcap,
        "turnover": round(vol / mcap, 4) if vol and mcap else None,
        "float_ratio": round(circ / maxs, 4) if circ and maxs else None,
        "dd_ath": round(cg["ath_chg"] / 100, 4) if cg.get("ath_chg") is not None
        else None,
        "mom_7d": round(cg["chg7d"] / 100, 4) if cg.get("chg7d") is not None else None,
        "mom_30d": round(cg["chg30d"] / 100, 4) if cg.get("chg30d") is not None
        else None,
        "tvl": tvl,
        "tvl_mcap": round(tvl / mcap, 4) if tvl and mcap else None,
    }


def onchain_metrics(symbols: list[str] | None = None) -> dict[str, dict]:
    """{symbole: métriques} pour les actifs demandés. Best-effort (sources sans clé)."""
    syms = symbols or list(COINS)
    ids = ",".join(COINS[s]["cg"] for s in syms if s in COINS)
    cg = parse_coingecko(_get_json(_CG.format(ids=ids)))
    chains = parse_llama_chains(_get_json(_LLAMA_CHAINS))
    out: dict[str, dict] = {}
    for s in syms:
        meta = COINS.get(s)
        if not meta:
            continue
        tvl = None
        if "chain" in meta:
            tvl = chains.get(meta["chain"].lower())
        elif "proto" in meta:
            tvl = _num(_get_json(_LLAMA_TVL.format(slug=meta["proto"])))
        out[s] = derive(cg.get(meta["cg"]), tvl)
    return out
