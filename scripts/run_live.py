"""Exécuteur live — réplique le portefeuille MODÈLE chez les brokers (DRY-RUN par défaut).

Routage : actions/ETF → **Alpaca (paper)** · crypto /USDC → **Bitmart** (ccxt).
Sécurité maximale :
  - DRY-RUN par défaut : affiche les ordres, n'envoie RIEN ;
  - mode réel uniquement avec `--live --yes` ET clés API présentes ;
  - Alpaca reste en **paper** (is_paper) ; Bitmart protégé par `dry_run` tant que `--live`
    n'est pas passé. Permissions API minimales, jamais de retrait.

  python scripts/run_live.py                 # aperçu (dry-run) des ordres cibles
  python scripts/run_live.py --live --yes    # envoie en paper/crypto (clés requises)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Réplique le portefeuille modèle (dry-run par défaut)")
    ap.add_argument("--live", action="store_true", help="envoyer réellement (sinon dry-run)")
    ap.add_argument("--yes", action="store_true", help="confirmation obligatoire pour le mode --live")
    ap.add_argument("--equity", type=float, default=None,
                    help="capital à allouer (dry-run) ; en live = equity réelle du broker")
    a = ap.parse_args()

    from apps.api.snapshot import build_snapshot
    from packages.core.models import Order, OrderType, Side

    targets = build_snapshot()["live"]["target_orders"]   # poids cibles (% du portefeuille)
    dry = not (a.live and a.yes)
    if a.live and not a.yes:
        print("⚠️  --live exige --yes (confirmation explicite). Abandon."); return

    # KILL-SWITCH : alertes TradingView (webhook) → veto / réduction d'exposition (sécurité live).
    from packages.mcp_tradingview.alerts import fetch_tv_technical_alerts, to_risk_veto
    risk = to_risk_veto(fetch_tv_technical_alerts())
    reduce = 0.0 if risk.get("veto") else float(risk.get("reduce", 1.0))
    if risk.get("veto"):
        print(f"⛔ KILL-SWITCH ACTIF (alertes TV critiques) : {', '.join(risk['reasons']) or '—'}")
        print("   → exposition forcée à 0, aucun ordre ne sera envoyé.")
    elif reduce < 1.0:
        print(f"⚠️  Alertes TV : exposition réduite ×{reduce:.2f} ({', '.join(risk['reasons']) or '—'})")

    alpaca = bitmart = None
    if not dry:
        from packages.execution.bitmart_broker import BitmartBroker
        bitmart = BitmartBroker(dry_run=False)
        try:
            from packages.execution.alpaca_broker import AlpacaBroker
            alpaca = AlpacaBroker(paper=True)             # actions TOUJOURS en paper
        except Exception as e:  # noqa: BLE001
            print(f"Alpaca indisponible ({str(e)[:60]}) → actions ignorées")

    # CAPITAL PAR COMPTE (comptes distincts) : actions ← Alpaca, crypto ← Bitmart.
    alp_cap = (alpaca.equity() if (alpaca and not dry) else 0.0) or a.equity or 10_000.0
    bit_cap = (bitmart.equity() if (bitmart and not dry) else 0.0) or 0.0
    print(f"Réplication · capital Alpaca {alp_cap:,.0f} $ · Bitmart {bit_cap:,.0f} $ · "
          f"mode {'DRY-RUN (aucun ordre)' if dry else 'LIVE (paper)'}")
    print(f"  {'SENS':4s} {'ACTIF':14s} {'BROKER':8s} {'POIDS':>7s} {'MONTANT':>10s}  statut")

    sent = 0
    for o in sorted(targets, key=lambda x: -x["weight_pct"]):
        cap = bit_cap if o.get("capital") == "bitmart" else alp_cap
        notional = o["weight_pct"] * cap * reduce          # kill-switch : ×0 (veto) … ×1 (normal)
        if reduce <= 0.0:                                   # veto total → on n'envoie rien
            print(f"  {o['side'].upper():4s} {o.get('broker_symbol', o['symbol']):14s} "
                  f"{o['broker']:8s} {o['weight_pct']*100:6.1f}% {'—':>9s}  bloqué (kill-switch)")
            continue
        side = Side.LONG if o["side"] == "long" else Side.SHORT
        broker = bitmart if o["broker"] == "Bitmart" else alpaca
        bsym = o.get("broker_symbol", o["symbol"])            # symbole côté broker (mapping)
        line = f"  {o['side'].upper():4s} {bsym:14s} {o['broker']:8s} {o['weight_pct']*100:6.1f}% {notional:9.0f}$"
        if o.get("tradeable") is False:                       # non négociable → jamais envoyé
            print(line + "  non négociable (sauté)")
            continue
        if dry or broker is None:
            print(line + "  " + ("aperçu" if dry else "broker absent"))
            continue
        try:
            # ordre par MONTANT $ dans les deux cas — le broker dérive/arrondit la quantité
            res = broker.submit_notional(bsym, side, notional)
            q = getattr(res, "qty", 0.0) or 0.0
            status = ("rejeté (min/précision)" if getattr(res, "status", None)
                      and str(res.status).endswith("REJECTED")
                      else (f"envoyé qty≈{q:.4f}" if q else "envoyé (paper)"))
            sent += 1
        except Exception as e:  # noqa: BLE001
            status = f"échec ({str(e)[:40]})"
        print(line + "  " + status)
    print(f"\nTerminé : {sent} ordres envoyés (paper)." if not dry else
          "\nAperçu (dry-run). Pour exécuter en paper : python3 scripts/run_live.py --live --yes")

    # CLÔTURE : synchronise le coffre Obsidian (journal + attribution + post-mortems).
    # Best-effort STRICT : ne lève jamais → ne peut pas bloquer l'exécution.
    try:
        from packages.reporting.obsidian import sync_obsidian_vault
        r = sync_obsidian_vault()
        print(f"Coffre Obsidian : {len(r.get('written', []))} note(s) · {r.get('incidents', 0)} incident(s).")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
