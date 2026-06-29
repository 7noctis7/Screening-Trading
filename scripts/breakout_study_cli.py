#!/usr/bin/env python3
"""Les cassures de canal BTC prédisent-elles un rendement ? Test au GATE placebo.

Réseau (prix BTC CoinGecko, gratuit). Confirmation on-chain en option (param). RIEN
câblé au ML tant que p ≥ 0,05. Écrit le verdict au ledger + note vault.
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.data.crypto_history import btc_price_history  # noqa: E402
from packages.research.breakout import significance  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--win", type=int, default=60)
    ap.add_argument("--post", type=int, default=5)
    ap.add_argument("--sims", type=int, default=1000)
    a = ap.parse_args()
    print("Téléchargement prix BTC (gratuit)…")
    closes = [v for _, v in btc_price_history()]
    print(f"  {len(closes)} jours")
    res = significance(closes, win=a.win, post=a.post, n_sims=a.sims)
    if not res.get("available"):
        print(f"⚠ indisponible (n={res.get('n')}, réseau ?)")
        return 1
    print(f"\n=== CASSURE DE CANAL BTC (win {a.win}, fwd {a.post}j) ===")
    print(f"events {res['n']} · CAR moyen {res['mean_car']} · t={res['t_stat']} · "
          f"p-placebo={res['placebo_p_value']} → {res['verdict']}")
    print("→ RIEN câblé au ML" if not res["significant"]
          else "→ candidat (à valider DSR/PBO/sabotage)")
    try:
        from packages.research.ledger import append_record
        append_record({"date": datetime.now(UTC).date().isoformat(),
                       "facteur": "breakout_canal_btc", "classe": ["crypto"],
                       "horizon": "swing",
                       "statut": "promu" if res["significant"] else "rejete",
                       "placebo_p_value": res["placebo_p_value"],
                       "these": f"Cassure canal BTC : CAR {res['mean_car']}, "
                                f"p={res['placebo_p_value']}, n={res['n']}."})
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
