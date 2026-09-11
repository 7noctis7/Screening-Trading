"""Artefact de modèle ML : entraînement DÉCOUPLÉ du serving (ticket #2, Huang/Musk).

Le modèle + ses métriques sont calculés hors-ligne (cron `make train`) puis sérialisés ; l'API
charge l'artefact au lieu de réentraîner à chaque requête. Garde-fou : si l'artefact est absent
ou périmé, le pipeline retombe sur un entraînement inline (jamais bloquant). pickle + TTL.
"""

from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path

_DIR = Path(__file__).resolve().parents[2] / "models"
_TTL = 86_400.0   # 24 h


def _key(signature) -> str:
    return hashlib.sha256(str(signature).encode()).hexdigest()[:16]


def metrics_payload(
    *, dsr: float | None, brier: float | None, auc: float | None
) -> dict:
    """Normalise les métriques OOS embarquées avec un modèle.

    Une métrique absente reste explicitement ``None`` : la remplacer par zéro ferait
    croire qu'un test a échoué alors qu'il n'a jamais été calculé, et permettrait à un
    futur promoteur de comparer des grandeurs imaginaires.
    """
    def finite(value: float | None) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    return {"dsr": finite(dsr), "brier": finite(brier), "auc": finite(auc)}


def metrics_from_payload(payload: object) -> dict:
    """Lit un payload ancien ou corrompu sans rendre le serving indisponible.

    Un artefact antérieur à ce contrat ne possède pas de métriques ; il doit rester
    chargeable, mais ne doit jamais être pris pour un champion comparable.
    """
    stored = payload.get("metrics") if isinstance(payload, dict) else None
    stored = stored if isinstance(stored, dict) else {}
    return metrics_payload(
        dsr=stored.get("dsr"), brier=stored.get("brier"), auc=stored.get("auc")
    )


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
