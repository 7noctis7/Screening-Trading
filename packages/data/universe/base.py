"""Sources de constituants d'univers — 1 source = 1 plugin auto-enregistré.

Une `ConstituentSource` renvoie une liste d'`Instrument`. Le `UniverseBuilder`
enchaîne toutes les sources activées (config YAML), dédoublonne et produit un
**snapshot daté** (membership point-in-time → anti survivorship-bias).

Sources offline (statiques) vs online (Wikipédia, CoinGecko, listings de bourse :
réseau requis, tournent dans l'environnement de l'utilisateur).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.core.models import Instrument
from packages.core.registry import Registry


@runtime_checkable
class ConstituentSource(Protocol):
    id: str
    requires_network: bool

    def fetch(self) -> list[Instrument]:
        ...


constituent_sources: Registry[ConstituentSource] = Registry("constituent_source")


class SourceError(Exception):
    pass
