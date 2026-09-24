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


sources: Registry[SourcePublications] = Registry("source_social")


def charger_plugins() -> list[str]:
    """Importe les modules du dossier pour déclencher leur auto-enregistrement."""
    for info in pkgutil.iter_modules(__path__):
        if not info.name.startswith("_"):
            importlib.import_module(f"{__name__}.{info.name}")
    return sources.names()
