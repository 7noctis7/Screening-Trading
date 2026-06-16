"""Vérifie le broker Alpaca PAPER dans TON environnement (réseau + clés requis).

  uv pip install alpaca-py
  export ALPACA_API_KEY=... ALPACA_API_SECRET=...
  python scripts/verify_alpaca.py

Se connecte en PAPER, lit le compte + positions. N'envoie PAS d'ordre par défaut.
Ajouter --order pour un MICRO-ordre paper de test (1 action AAPL). Jamais de réel ici.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    if not (os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_API_SECRET")):
        print("Clés ALPACA_API_KEY / ALPACA_API_SECRET absentes."); return 1
    from packages.execution.alpaca_broker import AlpacaBroker
    from packages.core.models import Order, Side
    from packages.execution import submit_with_retries
    broker = AlpacaBroker(paper=True)
    print(f"\nCompte PAPER : equity={broker.equity():,.0f}")
    print(f"Positions    : {[(p.instrument, p.qty) for p in broker.positions()]}")
    if "--order" in sys.argv:
        o = Order("AAPL", Side.LONG, 1, client_id=uuid.uuid4().hex)
        res = submit_with_retries(broker, o)
        print(f"Ordre paper test AAPL x1 → statut {res.status.value}")
    print("OK (paper, aucun ordre réel)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
