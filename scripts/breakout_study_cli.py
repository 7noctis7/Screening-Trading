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
from packages.research.breakout import full_gate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--win", type=int, default=60)
    ap.add_argument("--post", type=int, default=5)
    ap.add_argument("--sims", type=int, default=1000)
    a = ap.parse_args()
    print("Téléchargement prix BTC (gratuit)…")
    closes = [v for _, v in btc_price_history()]
    print(f"  {len(closes)} jours")
    if len(closes) < a.win + a.post + 30:
        print("⚠ historique trop court (réseau ?)")
        return 1
    g = full_gate(closes, win=a.win, post=a.post, n_sims=a.sims)
    print(f"\n=== CASSURE DE CANAL BTC — GATE COMPLET (win {a.win}, fwd {a.post}j) ===")
    print(f"1. placebo p   = {g['placebo_p']}   (< 0.05 ?)")
    print(f"2. DSR         = {g['dsr']}   (> 0.5 ? déflaté · {g['n_trials']} essais)")
    print(f"3. PBO         = {g['pbo']}   (< 0.5 ?)")
    sab = g["sabotage"]
    print(f"4. sabotage    = {'SURVIT' if sab.get('survives') else 'ÉCHOUE'}"
          f"   (rétention Sharpe {sab.get('sharpe_retention')})")
    print(f"\nVERDICT : {'🟢 PROMU' if g['promoted'] else '🔴 REJETÉ'}")
    if g["reasons"]:
        print("  recalé : " + " · ".join(g["reasons"]))
    if not g["promoted"]:
        print("→ RIEN câblé au ML/décision (le placebo seul ne suffit pas).")
    try:
        from packages.research.ledger import append_record
        append_record({"date": datetime.now(UTC).date().isoformat(),
                       "facteur": "breakout_canal_btc", "classe": ["crypto"],
                       "horizon": "swing",
                       "statut": "promu" if g["promoted"] else "rejete",
                       "dsr": g["dsr"], "pbo": g["pbo"],
                       "placebo_p_value": g["placebo_p"],
                       "these": f"Cassure canal BTC : DSR {g['dsr']}, PBO {g['pbo']}, "
                                f"placebo {g['placebo_p']}, sabotage "
                                f"{sab.get('survives')}."})
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
