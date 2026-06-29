"""make crypto-onchain — fondamentaux on-chain multi-sources (gratuit, sans clé).

Table des actifs : turnover, float, TVL, TVL/MCap, DD-ATH, momentum. CoinGecko (flow,
tous) + DefiLlama (TVL, chains/protocoles). Best-effort : '—' si une source manque.

  make crypto-onchain
  make crypto-onchain ARGS="--symbols BTC,ETH,SOL"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _r(x, nd=3):
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else "—"


def _pct(x):
    return f"{x * 100:+.1f}%" if isinstance(x, (int, float)) else "—"


def _tvl(x):
    return f"{x / 1e9:.2f}B" if isinstance(x, (int, float)) else "—"


def main() -> int:
    from packages.data.crypto_onchain import COINS, onchain_metrics
    ap = argparse.ArgumentParser(description="Fondamentaux on-chain crypto")
    ap.add_argument("--symbols", default=",".join(COINS))
    a = ap.parse_args()
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    print(f"Chargement on-chain (CoinGecko + DefiLlama) pour {len(syms)} actifs…")
    m = onchain_metrics(syms)
    if not m:
        print("❌ rien (réseau / sources indispo).")
        return 1
    head = f"{'sym':<7}{'turnover':>10}{'float':>8}{'TVL':>10}{'TVL/mcap':>10}" \
           f"{'DD-ATH':>9}{'mom30d':>9}"
    print("\n" + head)
    for s in syms:
        d = m.get(s, {})
        print(f"{s:<7}{_r(d.get('turnover')):>10}{_r(d.get('float_ratio'), 2):>8}"
              f"{_tvl(d.get('tvl')):>10}{_r(d.get('tvl_mcap')):>10}"
              f"{_pct(d.get('dd_ath')):>9}{_pct(d.get('mom_30d')):>9}")
    print("\nLecture : float bas = overhang d'unlocks · TVL/mcap haut = cap adossée à "
          "de l'activité réelle · DD-ATH = position dans le cycle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
