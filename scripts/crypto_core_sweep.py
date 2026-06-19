"""Cœur CRYPTO : BTC (le « QQQ de la crypto ») + satellite panier crypto diversifié.

Équivalent crypto de l'approche actions : on balaie X % BTC (cœur, l'actif dominant/benchmark) +
(1−X) % panier équipondéré des grandes capi crypto (satellite), et on regarde si un cœur BTC
améliore le couple rendement/risque. Données crypto via yfinance (BTC-USD, ETH-USD…) car la crypto
n'est PAS dans YAHOO.db (actions only). numpy pur.

  python scripts/crypto_core_sweep.py
  export QUANT_HISTORY_DAYS=3650   # fenêtre longue
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MAJORS = ["ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD"]


def main() -> None:
    import numpy as np
    from apps.api.snapshot import (_HISTORY_DAYS, _index_closes, datetime, timedelta, timezone)
    from packages.backtest.index_core import _stats, blend_equity

    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=_HISTORY_DAYS)
    print("Récupération des prix crypto (yfinance)…\n")
    btc, btc_real = _index_closes(["BTC-USD", "BTC/USDT", "BTC-USDC"], start, end, [])
    if not btc or len(btc) < 200:
        print("BTC indisponible (réseau yfinance ?)."); return

    baskets = []
    have = ["BTC"]
    for m in MAJORS:
        px, real = _index_closes([m], start, end, [])
        if real and len(px) > 200:
            baskets.append(np.asarray(px, float)); have.append(m.split("-")[0])
    if len(baskets) < 3:
        print("Pas assez de grandes capi crypto pour un panier (réseau ?)."); return

    L = min(len(b) for b in baskets)
    arr = np.asarray([b[-L:] for b in baskets])
    rets = arr[:, 1:] / arr[:, :-1] - 1
    basket_ret = rets.mean(axis=0)                       # panier équipondéré (rééq. quotidien)
    basket = np.concatenate([[100.0], 100.0 * np.cumprod(1 + basket_ret)])

    print(f"Panier satellite ({len(baskets)} actifs) : {', '.join(have[1:])}")
    print(f"Cœur : BTC ({'réel' if btc_real else 'repli'})\n")
    print(f"  {'BTC':>6s} {'Panier':>8s} {'CAGR':>8s} {'Sharpe':>7s} {'Sortino':>8s} {'maxDD':>8s} {'Calmar':>7s}")
    best = None
    for r in (0.0, 0.25, 0.5, 0.75, 1.0):
        eq, _ = blend_equity(list(basket), list(btc), r)   # core=BTC, satellite=panier
        if not eq:
            continue
        s = _stats(eq)
        print(f"  {r*100:5.0f}% {(1-r)*100:7.0f}% {s['cagr']*100:7.1f}% {s['sharpe']:7.2f} "
              f"{s['sortino']:8.2f} {s['max_drawdown']*100:7.1f}% {s.get('calmar', 0):7.2f}")
        if best is None or s["sharpe"] > best[1]:
            best = (r, s["sharpe"])
    print(f"\n  → meilleur Sharpe : {best[0]*100:.0f}% BTC + {(1-best[0])*100:.0f}% panier")
    print("\n  ⚠️ Crypto = très volatile, données yfinance, pas de correction biais du survivant.")
    print("  Bitmart ≈ 12 $ → impact réel marginal. Pour l'appliquer en prod il faut ingérer les")
    print("  prix crypto (hors YAHOO.db). À lire comme étude, pas comme signal d'allocation engageant.")


if __name__ == "__main__":
    main()
