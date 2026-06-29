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
    from packages.research.onchain_study import run_study
    ap = argparse.ArgumentParser(description="Étude alt-data on-chain (TVL/MCap)")
    ap.add_argument("--symbols", default=",".join(COINS))
    ap.add_argument("--post", type=int, default=5)
    ap.add_argument("--threshold", type=float, default=1.5)
    a = ap.parse_args()
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    print(f"Chargement historique on-chain (CoinGecko + DefiLlama) pour {len(syms)}…")
    res = run_study(syms, post=a.post, threshold=a.threshold)
    if not res.get("available"):
        print(f"❌ trop peu d'actifs avec TVL+historique ({res.get('n_assets', 0)}). "
              "Normal : peu de cryptos ont une série TVL exploitable.")
        return 1
    sig = res["significant"]
    verdict = "✅ SIGNIFICATIF (cross-actif)" if sig else "❌ NON significatif"
    print(f"\nOn-chain study · TVL/MCap · {res['n_assets']} actifs · "
          f"{res['n_events']} events · post={a.post}j")
    print(f"  CAR moyen poolé : {res['mean_car']*100:+.2f}%")
    print(f"  t-stat          : {res['t_stat']}")
    print(f"  p-value placebo : {res['placebo_p_value']}")
    print(f"  → {verdict}")
    print("  GO backtest net + DSR/PBO." if sig
          else "  STOP : pas d'edge prouvé (attendu vu l'échantillon mince).")
    _log(a, res)
    return 0


def _log(a, res: dict) -> None:
    try:
        from packages.research.ledger import append_record
        append_record({
            "date": datetime.now(UTC).date().isoformat(),
            "facteur": "onchain_tvl_mcap", "classe": ["crypto"], "horizon": "swing",
            "dsr": None, "pbo": res["placebo_p_value"],
            "statut": "en_test" if res["significant"] else "rejete",
            "these": f"TVL/MCap cross-actif ({res['n_assets']} cryptos) : "
                     f"CAR {res['mean_car']*100:+.2f}%, p={res['placebo_p_value']}.",
        })
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    raise SystemExit(main())
