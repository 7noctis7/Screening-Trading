"""make onchain-study — le TVL/MCap prédit-il les rendements crypto ? (gate placebo).

Historique gratuit (CoinGecko + DefiLlama) → event-study cross-actif sur le z-score du
facteur + placebo. Le seul juge = la p-value placebo. Loggue au ledger.

  make onchain-study
  make onchain-study ARGS="--symbols BTC,ETH,SOL,NEAR --post 5"
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from packages.data.crypto_onchain import COINS
    from packages.research.onchain_study import FACTORS, run_study
    ap = argparse.ArgumentParser(description="Étude alt-data on-chain (multi-facteurs)")
    ap.add_argument("--symbols", default=",".join(COINS))
    ap.add_argument("--factors", default=",".join(FACTORS),
                    help="facteurs à tester (tvl_mcap, fees_mcap)")
    ap.add_argument("--post", type=int, default=5)
    ap.add_argument("--threshold", type=float, default=1.5)
    a = ap.parse_args()
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    factors = [f.strip() for f in a.factors.split(",") if f.strip()]
    print(f"Chargement historique on-chain (CoinGecko + DefiLlama) pour {len(syms)}…")
    any_ok = False
    for factor in factors:
        res = run_study(syms, factor=factor, post=a.post, threshold=a.threshold)
        if not res.get("available"):
            print(f"\n[{factor}] ❌ trop peu d'actifs ({res.get('n_assets', 0)}) "
                  "avec série exploitable.")
            _log(factor, res)
            continue
        any_ok = True
        sig = res["significant"]
        verdict = "✅ SIGNIFICATIF (cross-actif)" if sig else "❌ NON significatif"
        print(f"\n[{factor}] {res['n_assets']} actifs · {res['n_events']} events · "
              f"post={a.post}j")
        print(f"  CAR moyen poolé : {res['mean_car']*100:+.2f}%")
        print(f"  t-stat          : {res['t_stat']}")
        print(f"  p-value placebo : {res['placebo_p_value']}")
        print(f"  → {verdict}"
              + ("  GO backtest net + DSR/PBO." if sig else "  STOP (attendu)."))
        _log(factor, res)
    return 0 if any_ok else 1


def _log(factor: str, res: dict) -> None:
    try:
        from packages.research.ledger import append_record
        avail = res.get("available")
        append_record({
            "date": datetime.now(UTC).date().isoformat(),
            "facteur": f"onchain_{factor}", "classe": ["crypto"], "horizon": "swing",
            "dsr": None, "pbo": res.get("placebo_p_value"),
            "statut": ("en_test" if avail and res["significant"] else "rejete"),
            "these": (f"{factor} cross-actif ({res.get('n_assets', 0)} cryptos) : "
                      f"CAR {res.get('mean_car', 0)*100:+.2f}%, "
                      f"p={res.get('placebo_p_value')}."),
        })
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    raise SystemExit(main())
