#!/usr/bin/env python3
"""Teste le Fear & Greed comme signal contrarian BTC, au GATE placebo.

Réseau requis (CoinGecko + alternative.me, gratuit, sans clé). Écrit le verdict dans
le ledger d'hypothèses + une note vault. AUCUN câblage ML/décision ici : tant que le
gate n'est pas franchi, le F&G reste du CONTEXTE (cf. manifeste d'honnêteté).
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.data.crypto_history import btc_price_history, fng_history  # noqa: E402
from packages.research.regime_study import run_fng_study  # noqa: E402


def _blurb(sig) -> str:
    return ("signal exploitable, candidat overlay régime" if sig
            else "bruit : rien câblé (6e négatif propre)")


def _note(res: dict) -> None:
    try:
        d = ROOT / "vault" / "10_Backtests"
        d.mkdir(parents=True, exist_ok=True)
        today = datetime.now(UTC).date().isoformat()
        sig = res.get("significant")
        (d / "Regime_FearGreed.md").write_text(
            f"---\ntype: regime_study\nfacteur: fear_greed_contrarian\n"
            f"placebo_p: {res.get('placebo_p_value')}\n"
            f"significant: {bool(sig)}\ndate: {today}\n---\n\n"
            f"# 🌡️ F&G contrarian sur BTC ({today})\n\n"
            f"{res.get('n_days', '?')} jours communs "
            f"({res.get('start', '?')} → {res.get('end', '?')}), "
            f"fenêtre forward {res.get('post')}j, seuil |z|>{res.get('threshold')}.\n\n"
            f"- Events extrêmes : **{res.get('n', '?')}**\n"
            f"- CAR signé moyen : **{res.get('mean_car')}**\n"
            f"- t-stat : **{res.get('t_stat')}**\n"
            f"- p-value placebo : **{res.get('placebo_p_value')}**\n\n"
            f"Verdict : **{res.get('verdict', 'n/d')}** — "
            f"{_blurb(sig)}.\n",
            encoding="utf-8")
        print("  📝 note → vault/10_Backtests/Regime_FearGreed.md")
    except OSError:
        pass


def _ledger(res: dict) -> None:
    try:
        from packages.research.ledger import append_record
        append_record({
            "date": datetime.now(UTC).date().isoformat(),
            "facteur": "fear_greed_contrarian", "classe": ["crypto"],
            "horizon": "swing",
            "statut": "promu" if res.get("significant") else "rejete",
            "placebo_p_value": res.get("placebo_p_value"),
            "these": (f"F&G contrarian BTC : CAR {res.get('mean_car')}, "
                      f"p={res.get('placebo_p_value')}, n={res.get('n')}."),
        })
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", type=int, default=5, help="fenêtre forward (jours)")
    ap.add_argument("--threshold", type=float, default=1.5, help="seuil |z|")
    ap.add_argument("--sims", type=int, default=1000, help="simulations placebo")
    a = ap.parse_args()

    print("Téléchargement F&G + prix BTC (gratuit, sans clé)…")
    fng = fng_history()
    btc = btc_price_history()
    print(f"  F&G : {len(fng)} jours · BTC : {len(btc)} jours")
    res = run_fng_study(fng, btc, post=a.post, threshold=a.threshold, n_sims=a.sims)
    if not res.get("available"):
        print(f"⚠ indisponible : {res.get('reason')} (sources injoignables ?)")
        return 1

    print(f"\n=== F&G CONTRARIAN sur BTC ({res['start']} → {res['end']}) ===")
    print(f"events |z|>{a.threshold} : {res['n']} · CAR moyen {res['mean_car']} · "
          f"t={res['t_stat']} · p-placebo={res['placebo_p_value']}")
    print(f"VERDICT : {res['verdict']}")
    if not res["significant"]:
        print("→ bruit : RIEN câblé au ML/décision (6e négatif honnête).")
    else:
        print("→ candidat overlay de RÉGIME (pas alpha) — à valider DSR/PBO.")
    _note(res)
    _ledger(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
