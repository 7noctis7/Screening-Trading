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

# Mode LÉGER pour l'exécution (`run_live`) : ces sections coûteuses (réseau : news, ML,
# marchés de prédiction, on-chain…) ne servent PAS à la réconciliation, qui n'a besoin
# que
# des poids cibles + régime + prix. QUANT_LIVE_LITE=1 les court-circuite → le snapshot
# de
# décision passe de plusieurs minutes (souvent interrompu) à quelques secondes.
# Les sections NÉCESSAIRES au live (screen, ticker via prix, honesty…) ne sont PAS ici.
#
# `fundamentals` EN EST SORTIE le 27/08 — elle n'était pas « non essentielle », elle
# décidait de l'univers.
#
# Mesuré en production, même capital, même minute :
#   mode léger    → « 0 scoré → repli MOMENTUM », 12 noms, régime 0.000, satellite VIDE
#   mode complet  → 12 actions réelles (THC, UNP, TGT, TMO, T…), 75 720 $ alloués
# Le score qualité alimente la sélection d'univers. Sans lui, le repli prend le top-12
# du
# momentum à 12 mois — c'est-à-dire, par construction, les douze titres les plus
# extrêmes
# de l'univers. L'indice de ce panier est presque toujours à plus de 15 % sous son
# pic, ce
# qui met la porte de RÉGIME à zéro. Le satellite actions était donc structurellement
# vide
# en exécution, et cela n'avait rien à voir avec le marché.
#
# COÛT ASSUMÉ : le snapshot de décision repasse de ~30 s à quelques minutes. Acceptable
# parce que le rebalancement tourne sous cron, sans personne devant l'écran, et surtout
# parce que la DÉGRADATION EST GRACIEUSE : `safe_section` isole toute panne de
# section, un
# échec de `fundamentals` rend `{available: False}` et la sélection retombe sur le
# momentum
# — c'est-à-dire exactement le comportement d'avant. Le pire cas du correctif est l'état
# antérieur ; le meilleur, un satellite actions qui existe.
#
# Pour revenir en arrière sans toucher au code : QUANT_LIVE_LITE_SKIP_FUNDAMENTALS=1.
_LITE_SKIP = frozenset({
    "investors", "conviction", "sentiment", "ml", "themes",
    "crypto_cockpit", "events", "analytics",
})


def _saute_en_mode_leger(name: str) -> bool:
    """Cette section doit-elle être court-circuitée ? Échappatoire explicite incluse."""
    if os.environ.get("QUANT_LIVE_LITE") != "1":
        return False
    if (name == "fundamentals"
            and os.environ.get("QUANT_LIVE_LITE_SKIP_FUNDAMENTALS") == "1"):
        return True                      # retour au comportement d'avant le 27/08
    return name in _LITE_SKIP


def safe_section(name: str, fn: Callable[..., dict], *args: Any, **kwargs: Any) -> dict:
    """Execute `fn(*args, **kwargs)` en isolant toute exception.

    Succes -> resultat tel quel. Echec -> fallback `{available: False, error, section}`
    (jamais propage) : les autres sections et le snapshot global survivent.
    En mode `QUANT_LIVE_LITE=1`, les sections non essentielles à l'exécution sont
    court-circuitées (retour immédiat `available: False`) — snapshot de décision rapide.
    """
    if _saute_en_mode_leger(name):
        return {"available": False, "section": name, "skipped": "live-lite"}
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 - isolation volontaire de toute panne
        log.warning("section %r KO -> fallback (%s: %s)", name, type(e).__name__, e)
        err = f"{type(e).__name__}: {e}"
        return {"available": False, "error": err, "section": name}
