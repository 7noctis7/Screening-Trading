#!/usr/bin/env python3
"""Cockpit crypto en ligne de commande — vue marché agrégée (gratuit, sans clé).

Tape les sources publiques (CoinGecko, DefiLlama, alternative.me) et affiche un résumé
scannable. Best-effort : "n/d" si une source tombe (jamais de chiffre inventé).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.data.crypto_market import cockpit  # noqa: E402


def _usd(x) -> str:
    if not isinstance(x, (int, float)):
        return "n/d"
    for div, suf in ((1e12, " T"), (1e9, " Md"), (1e6, " M")):
        if x >= div:
            return f"${x / div:.2f}{suf}"
    return f"${x:,.0f}"


def main() -> int:
    ck = cockpit()
    g = ck.get("global") or {}
    se = ck.get("sentiment") or {}
    fng = ck.get("fng") or {}
    defi = ck.get("defi") or {}

    print("=== COCKPIT CRYPTO ===")
    if se.get("available"):
        print(f"Humeur : {se['label']}  ({se['score']}/100)")
        for d in se.get("drivers", []):
            print(f"  · {d}")
    print(f"Cap totale     : {_usd(g.get('total_mcap'))}  "
          f"(24 h {g.get('mcap_chg_24h', 'n/d')}%)")
    btc = g.get("btc_dom")
    eth = g.get("eth_dom")
    print(f"Dominance      : BTC {btc if btc is not None else 'n/d'}%  "
          f"ETH {eth if eth is not None else 'n/d'}%")
    if fng.get("available"):
        print(f"Fear & Greed   : {fng.get('value')} ({fng.get('label')})")
    print(f"TVL DeFi       : {_usd(defi.get('total_tvl'))}")

    cats = ck.get("categories") or []
    if cats:
        print("\nNarratifs (24 h) :")
        for c in cats[:6]:
            print(f"  {c['name']:<22} {c['chg24h']:+.1f}%")

    gain = ck.get("gainers") or []
    lose = ck.get("losers") or []
    if gain or lose:
        print("\nGagnants / Perdants 24 h :")
        for m in gain[:5]:
            print(f"  📈 {m['sym']:<6} {m.get('chg24h', 0):+.1f}%")
        for m in lose[:5]:
            print(f"  📉 {m['sym']:<6} {m.get('chg24h', 0):+.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
