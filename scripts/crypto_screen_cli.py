#!/usr/bin/env python3
"""Screener crypto en langage naturel — text-to-filter DÉTERMINISTE.

  make crypto-screen Q="cap > 5 milliards et hausse > 3% top 10"
Le parseur traduit la requête en params ; le CODE filtre (jamais le LLM) → 0 invention.
Réseau : top 100 CoinGecko (gratuit). Note : les filtres 'funding' n'ont de données que
pour BTC/ETH/SOL (dérivés) ; sur la liste marché, utilise cap/hausse/baisse/top.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.data.crypto_market import _MARKETS, _get_json, parse_markets  # noqa: E402
from packages.research.crypto_query import apply_filter, parse_query  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="requête en langage naturel")
    a = ap.parse_args()
    params = parse_query(a.query)
    print(f"Requête : {a.query}")
    print(f"Params  : {params or '(aucun filtre reconnu → tout, trié par cap)'}\n")
    markets = parse_markets(_get_json(_MARKETS))
    if not markets:
        print("⚠ marché injoignable (réseau).")
        return 1
    rows = apply_filter(markets, params)
    if not rows:
        print("(aucun actif ne correspond)")
        return 0
    print(f"{'#':>3}  {'SYM':<8}{'PRIX':>14}{'24H':>9}{'CAP':>12}")
    for i, r in enumerate(rows[:25], 1):
        cap = r.get("mcap") or 0
        caps = f"{cap/1e9:.1f}Md" if cap >= 1e9 else f"{cap/1e6:.0f}M"
        chg = r.get("chg24h")
        print(f"{i:>3}  {r['sym']:<8}{(r.get('price') or 0):>14,.4f}"
              f"{(chg if chg is not None else 0):>8.1f}%{caps:>12}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
