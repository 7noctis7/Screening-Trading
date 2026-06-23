"""Isolation des fautes par section (antifragilite du snapshot).

Une section qui leve une exception ne doit JAMAIS tuer le snapshot entier (bug
historique : un IndexError macro vidait tout le site). `safe_section()` capture la
panne, la journalise, et renvoie un fallback structure (`available: False`). Le
chemin heureux est strictement inchange. C'est la "andon cord" applicative.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)


def safe_section(name: str, fn: Callable[..., dict], *args: Any, **kwargs: Any) -> dict:
    """Execute `fn(*args, **kwargs)` en isolant toute exception.

    Succes -> resultat tel quel. Echec -> fallback `{available: False, error, section}`
    (jamais propage) : les autres sections et le snapshot global survivent.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 - isolation volontaire de toute panne
        log.warning("section %r KO -> fallback (%s: %s)", name, type(e).__name__, e)
        err = f"{type(e).__name__}: {e}"
        return {"available": False, "error": err, "section": name}
