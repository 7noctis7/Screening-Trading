"""Mémoïsation d'étapes par EMPREINTE DE CONTENU (snapshot incrémental — #4).

Ne recalcule une étape PURE et coûteuse que si ses entrées ont changé. Sinon, on relit le
résultat persisté (`.cache/stages/`). 100 % best-effort : toute erreur (cache illisible, disque
plein, version changée) → on recalcule, jamais de plantage. Persistance via `safe_pickle`
(anti-symlink + empreinte SHA-256). Désactivable par `QUANT_STAGE_CACHE=0`.

⚠️ À n'utiliser que sur des fonctions DÉTERMINISTES (mêmes entrées → même sortie), sans effet
de bord ni dépendance au temps/réseau.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from packages.common import safe_pickle

_DIR = Path(__file__).resolve().parents[2] / ".cache" / "stages"


def _enc(o: Any):
    try:
        import numpy as np
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.generic):
            return o.item()
    except Exception:  # noqa: BLE001
        pass
    return str(o)


def fingerprint(inputs: Any) -> str:
    """Empreinte stable et compacte des entrées (sha256 tronqué)."""
    blob = json.dumps(inputs, default=_enc, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _enabled() -> bool:
    return os.environ.get("QUANT_STAGE_CACHE", "1").lower() not in ("0", "false", "no")


def cached_stage(name: str, inputs: Any, compute: Callable[[], Any], *, version: str = "1") -> Any:
    """Renvoie le résultat de `compute()` mémoïsé par (name, version, empreinte(inputs)).

    Recalcule si l'entrée a changé, si la version a changé, ou si le cache est indisponible.
    Ne conserve qu'UN fichier par `name` (le dernier) → répertoire borné."""
    if not _enabled():
        return compute()
    try:
        key = f"{name}-{version}-{fingerprint(inputs)}"
        path = _DIR / f"{key}.pkl"
        if path.exists():
            try:
                return safe_pickle.load(path)
            except Exception:  # noqa: BLE001 — cache corrompu/altéré → on recalcule
                pass
        res = compute()
        try:
            _DIR.mkdir(parents=True, exist_ok=True)
            safe_pickle.dump(res, path)
            for old in _DIR.glob(f"{name}-*.pkl"):          # garde uniquement le dernier (borne le disque)
                if old.name != path.name:
                    old.unlink(missing_ok=True)
                    old.with_suffix(old.suffix + ".sha256").unlink(missing_ok=True)
        except Exception:  # noqa: BLE001 — disque indisponible → on n'a pas persisté, tant pis
            pass
        return res
    except Exception:  # noqa: BLE001 — l'accélérateur ne doit JAMAIS casser le pipeline
        return compute()
