"""Chargement des CAPITALISATIONS BOURSIÈRES (market cap) pour pondérer/classer le panier
méga-caps « comme un vrai indice ». Stockage SIDECAR (data/market_caps.json) — non destructif,
indépendant de YAHOO.db (qui est ouverte en lecture seule et de schéma variable).

Format du fichier :
  { "AAPL": {"current": 3.1e12, "history": [["2020-01-02", 17.0e9], ...]}, ... }
  history = nombre d'ACTIONS en circulation à diverses dates (forward-fill) → market cap(t) =
  actions_asof(t) × close(t). Si pas d'historique, on utilise "current" (proxy constant).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_DEFAULT = ROOT / "data" / "market_caps.json"


def market_cap_path() -> Path:
    return Path(os.environ.get("QUANT_MKTCAP_FILE", str(_DEFAULT)))


def load_market_caps(path: str | Path | None = None) -> dict:
    """Charge le sidecar {symbole -> {current, history}} ; {} si absent/illisible."""
    p = Path(path) if path else market_cap_path()
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text())
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def shares_asof(record: dict, dates: list) -> np.ndarray:
    """Actions en circulation alignées sur `dates` (iso str ou datetime), forward-fill depuis
    l'historique ; repli sur `current` ; NaN si rien."""
    out = np.full(len(dates), np.nan, dtype=float)
    hist = record.get("history") or []
    pts = sorted(((str(d)[:10], float(s)) for d, s in hist if s), key=lambda x: x[0]) if hist else []
    if pts:
        di = [d for d, _ in pts]
        sv = [s for _, s in pts]
        j = 0
        for i, d in enumerate(dates):
            ds = str(d if not hasattr(d, "isoformat") else d.isoformat())[:10]
            while j + 1 < len(di) and di[j + 1] <= ds:
                j += 1
            out[i] = sv[j]
    elif record.get("current"):
        out[:] = float(record["current"])
    return out
