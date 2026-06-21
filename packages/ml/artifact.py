"""Artefact de modèle ML : entraînement DÉCOUPLÉ du serving (ticket #2, Huang/Musk).

Le modèle + ses métriques sont calculés hors-ligne (cron `make train`) puis sérialisés ; l'API
charge l'artefact au lieu de réentraîner à chaque requête. Garde-fou : si l'artefact est absent
ou périmé, le pipeline retombe sur un entraînement inline (jamais bloquant). pickle + TTL.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

_DIR = Path(__file__).resolve().parents[2] / "models"
_TTL = 86_400.0   # 24 h


def _key(signature) -> str:
    return hashlib.sha256(str(signature).encode()).hexdigest()[:16]


def save(signature, model, payload: dict) -> bool:
    try:
        from packages.common import safe_pickle
        safe_pickle.dump({"model": model, "payload": payload, "ts": time.time()},
                         _DIR / f"ml_{_key(signature)}.pkl")   # + sidecar .sha256 (provenance)
        return True
    except Exception:  # noqa: BLE001
        return False


def load(signature, ttl: float = _TTL):
    """Renvoie (model, payload) si un artefact frais existe, sinon None.
    Durci : refuse symlink + vérifie l'empreinte SHA-256 (artefact ML potentiellement partagé)."""
    try:
        from packages.common import safe_pickle
        p = _DIR / f"ml_{_key(signature)}.pkl"
        if not p.exists() or time.time() - p.stat().st_mtime > ttl:
            return None
        d = safe_pickle.load(p)
        return d["model"], d["payload"]
    except Exception:  # noqa: BLE001
        return None
