#!/usr/bin/env python3
"""Diagnostic Bitmart LECTURE SEULE (BLOC 2) — pourquoi aucun trade ne part, verrou par verrou.

  make bitmart-check    # n'envoie JAMAIS d'ordre ; lit solde/positions si clés présentes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.common.env import load_env  # noqa: E402

load_env()
k, s_, m = (os.environ.get(x, "") for x in
            ("BITMART_API_KEY", "BITMART_API_SECRET", "BITMART_API_MEMO"))
print("VERROUS (aucun n'est un bug — cf. ADR-0032 : ère mono-broker Alpaca) :")
print(f"  1. dry_run par défaut          : ACTIF (BitmartBroker(dry_run=True) sans --live)")
print(f"  2. QUANT_NO_CRYPTO_LIVE        : {os.environ.get('QUANT_NO_CRYPTO_LIVE', '1 (défaut)')} "
      f"→ le cron RETIRE les clés Bitmart de l'environnement")
print(f"  3. Routage crypto (ADR-0032)   : BTC/ETH → Alpaca PAPER ; Bitmart = adaptateur futur-live")
print(f"  Clés .env : key={'✓' if k else '✗'} secret={'✓' if s_ else '✗'} memo={'✓' if m else '✗'}"
      + ("" if m or not k else "  ⚠️ MEMO obligatoire chez BitMart (X-BM-MEMO) — sans lui, auth KO"))
if not (k and s_):
    print("→ Pas de clés : connexion non testable (normal si Bitmart désactivé). Aucun ordre envoyé.")
    sys.exit(0)
from packages.execution.bitmart_broker import BitmartBroker  # noqa: E402

b = BitmartBroker(dry_run=False)                       # lecture seule : AUCUN submit ici
try:
    eq = b.equity()
    pos = b.positions_detailed()
    print(f"→ Connexion OK (lecture seule) : equity {eq:,.2f} $ · {len(pos)} position(s) spot")
    for p in pos[:10]:
        print(f"   {p['symbol']:12s} qty {p['qty']:.6f} ≈ {p.get('market_value', 0):,.2f} $")
except Exception as e:  # noqa: BLE001
    print(f"→ ÉCHEC connexion : {str(e)[:120]}")
    print("   Pistes : memo manquant/faux · clés expirées · IP non autorisée côté BitMart.")
    sys.exit(1)
print("Rappel : activation trading Bitmart = décision explicite post-RDV 2026-08-06 (CLAUDE.md).")
