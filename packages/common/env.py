"""Chargeur `.env` minimal (stdlib, aucune dépendance).

Lit le fichier `.env` à la racine du dépôt et peuple `os.environ` SANS écraser les variables
déjà définies (l'environnement réel reste prioritaire). Appelé au démarrage (API, scripts) pour
que les clés Alpaca/Bitmart/FMP et options (QUANT_PRICE_DB, QUANT_NEWS, LLM_*) soient prises en
compte automatiquement après un simple `cp .env.example .env`.
"""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]   # packages/common/env.py → racine du dépôt


def load_env(path: str | Path | None = None) -> int:
    """Charge le `.env` (racine du dépôt par défaut). Renvoie le nb de variables ajoutées."""
    f = Path(path) if path else _ROOT / ".env"
    if not f.exists():
        return 0
    added = 0
    for raw in f.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:          # ne jamais écraser l'env réel
            os.environ[key] = val
            added += 1
    return added
