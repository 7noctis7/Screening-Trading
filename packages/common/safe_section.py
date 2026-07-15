"""Isolation des fautes par section (antifragilite du snapshot).

Une section qui leve une exception ne doit JAMAIS tuer le snapshot entier (bug
historique : un IndexError macro vidait tout le site). `safe_section()` capture la
panne, la journalise, et renvoie un fallback structure (`available: False`). Le
chemin heureux est strictement inchange. C'est la "andon cord" applicative.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

# Mode LÉGER pour l'exécution (`run_live`) : ces sections coûteuses (réseau : fondamentaux,
# news, ML, marchés de prédiction, on-chain…) ne servent PAS à la réconciliation, qui n'a
# besoin que des poids cibles + régime + prix. QUANT_LIVE_LITE=1 les court-circuite → le
# snapshot de décision passe de plusieurs minutes (souvent interrompu) à quelques secondes.
# Les sections NÉCESSAIRES au live (screen, ticker via prix, honesty…) ne sont PAS ici.
_LITE_SKIP = frozenset({
    "fundamentals", "investors", "conviction", "sentiment", "ml", "themes",
    "crypto_cockpit", "events", "analytics",
})


def safe_section(name: str, fn: Callable[..., dict], *args: Any, **kwargs: Any) -> dict:
    """Execute `fn(*args, **kwargs)` en isolant toute exception.

    Succes -> resultat tel quel. Echec -> fallback `{available: False, error, section}`
    (jamais propage) : les autres sections et le snapshot global survivent.
    En mode `QUANT_LIVE_LITE=1`, les sections non essentielles à l'exécution sont
    court-circuitées (retour immédiat `available: False`) — snapshot de décision rapide.
    """
    if name in _LITE_SKIP and os.environ.get("QUANT_LIVE_LITE") == "1":
        return {"available": False, "section": name, "skipped": "live-lite"}
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 - isolation volontaire de toute panne
        log.warning("section %r KO -> fallback (%s: %s)", name, type(e).__name__, e)
        err = f"{type(e).__name__}: {e}"
        return {"available": False, "error": err, "section": name}
