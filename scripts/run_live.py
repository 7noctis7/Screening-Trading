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
    a = ap.parse_args()

    from apps.api.snapshot import build_snapshot
    from packages.core.models import Order, OrderType, Side

    snap = build_snapshot()
    targets = snap["live"]["target_orders"]
    kpis = snap["live"]["portfolio"]
    dry = not (a.live and a.yes)
    print(f"Portefeuille modèle : {kpis.get('value')} $ · {len(targets)} lignes · "
          f"mode {'DRY-RUN (aucun ordre envoyé)' if dry else 'LIVE'}")
    if a.live and not a.yes:
        print("⚠️  --live exige --yes (confirmation). Abandon."); return

    # brokers (instanciés à la demande, sûrs)
    alpaca = bitmart = None
    if not dry:
        from packages.execution.bitmart_broker import BitmartBroker
        bitmart = BitmartBroker(dry_run=False)
        try:
            from packages.execution.alpaca_broker import AlpacaBroker
            alpaca = AlpacaBroker(paper=True)        # TOUJOURS paper
        except Exception as e:  # noqa: BLE001
            print(f"Alpaca indisponible ({str(e)[:60]}) → actions en dry-run")

    sent = 0
    for o in targets:
        broker = bitmart if o["broker"] == "Bitmart" else alpaca
        line = f"  {o['side'].upper():4s} {o['symbol']:14s} {o['broker']:8s} ~{o['weight_value']:>8.0f} $"
        if dry or broker is None:
            print(("DRY  " if dry else "SKIP ") + line)
            continue
        order = Order(o["symbol"], Side.LONG if o["side"] == "long" else Side.SHORT,
                      qty=0.0, order_type=OrderType.MARKET)   # qty calculée par le broker réel
        res = broker.submit(order)
        print(f"SENT {line} → {getattr(res, 'status', '?')}")
        sent += 1
    print(f"Terminé : {sent} ordres envoyés." if not dry else
          "Aperçu terminé (dry-run). Relancer avec --live --yes pour exécuter.")


if __name__ == "__main__":
    main()
