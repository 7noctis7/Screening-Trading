"""Détection de connectivité réseau (rapide, sans dépendance) → permet d'utiliser les données
réelles PAR DÉFAUT tout en dégradant instantanément hors-ligne (jamais de blocage)."""

from __future__ import annotations

import socket
import time

_CACHE: tuple[float, bool] | None = None
_TTL = 30.0   # on ne re-teste pas plus d'une fois toutes les 30 s


def online(host: str = "8.8.8.8", port: int = 53, timeout: float = 1.0) -> bool:
    """True si une connexion sortante aboutit en < timeout s (DNS Google par défaut). Caché 30 s."""
    global _CACHE
    now = time.time()
    if _CACHE and now - _CACHE[0] < _TTL:
        return _CACHE[1]
    ok = False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ok = True
    except OSError:
        ok = False
    _CACHE = (now, ok)
    return ok
