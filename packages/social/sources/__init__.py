"""Registre des sources de publications. Ajouter une source = UN fichier ici.

Conformément à la règle du dépôt (AGENTS.md §5.2), brancher un nouveau moyen de
récupérer des publications — API X payante, export d'un client tiers, copier-coller —
ne doit RIEN changer au reste : un fichier qui s'auto-enregistre, et c'est tout.

Ce que le registre permet surtout, c'est de dire la vérité quand il n'y a rien : une
source qui ne rend aucune publication rend une liste vide, jamais un jeu d'exemples.
L'onglet affiche alors « flux non connecté » — un écran honnête vaut mieux qu'un écran
plein de données inventées, qu'on finirait par prendre pour des vraies.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Protocol, runtime_checkable

from packages.core.registry import Registry
from packages.social.modele import Publication


@runtime_checkable
class SourcePublications(Protocol):
    """Rend ce qu'elle a lu. Une source vide rend `[]` — jamais un échantillon."""

    def lire(self) -> list[Publication]: ...


def est_configuree(source: object) -> bool:
    """Une source sait seule si elle a de quoi travailler. Le shell ne le sait pas.

    Les gardes avaient d'abord été écrites dans `cron_daily.sh`, sous la forme
    `[ -n "${QUANT_TG_CANAUX:-}" ]`. C'était FAUX sans que rien ne le dise : `.env`
    n'est lu qu'en Python (`packages/common/env.py`), donc sous cron ces variables sont
    vides, la garde échoue, et les trois sources sont sautées EN SILENCE — chaque nuit,
    indéfiniment. Une garde censée éviter un log bruyant serait devenue la raison pour
    laquelle la tâche ne tourne jamais, sans une ligne pour le signaler.

    La question « ai-je de quoi lire ? » n'a donc qu'UN endroit où se poser : la source.

    Défaut à `True` : un plugin tiers qui ne déclare rien est réputé configuré. Le
    supposer non configuré le rendrait muet, et l'auteur du plugin n'aurait aucun
    moyen de comprendre pourquoi sa source ne tourne pas.
    """
    return bool(getattr(source, "configuree", True))


sources: Registry[SourcePublications] = Registry("source_social")


def charger_plugins() -> list[str]:
    """Importe les modules du dossier pour déclencher leur auto-enregistrement."""
    for info in pkgutil.iter_modules(__path__):
        if not info.name.startswith("_"):
            importlib.import_module(f"{__name__}.{info.name}")
    return sources.names()
