"""La place de marché crypto est un CHOIX, pas un nom codé en dur.

Le second courtier était nommé « bitmart » dans une trentaine de fichiers — script d'exécution,
garde-fous, payload de l'API, cinq pages du front, grille de frais, tests. Changer de place
supposait donc de renommer partout, avec la certitude d'en oublier. Ce module isole ce que la
place EST (nom affiché, clés d'environnement, fabrique du courtier, barème) de ce que le reste
du code en FAIT.

Bascule par `QUANT_CRYPTO_VENUE`. Défaut : Binance — taker à 0,10 % contre 0,25 % chez Bitmart,
soit des frais crypto divisés par 2,5 à rotation égale, et un carnet plus profond donc moins de
glissement. Bitmart reste disponible, sans code mort.

Rappel de garde-fou : ce module ne fait qu'INSTANCIER. Aucune place n'envoie d'ordre réel sans
`--live --yes` et sans clés présentes ; la crypto de l'ère paper reste routée vers Alpaca
(cf. ADR-0029 et packages/execution/routing).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Venue:
    cle: str                          # identifiant interne, stable dans les payloads
    nom: str                          # nom affiché
    env: tuple[str, ...]              # variables d'environnement attendues
    portee: str                       # ce que la place couvre, en clair
    testnet_env: str | None = None    # variable qui force le bac à sable, si la place en a un
    notes: str = ""
    _fabrique: str = field(default="", repr=False)   # module:classe, importé à la demande

    def configuree(self) -> bool:
        """Les clés sont-elles présentes ? Une place sans clés n'est jamais instanciée."""
        return all(os.environ.get(k) for k in self.env)

    def broker(self, dry_run: bool = True):
        """Instancie le courtier. Lève si la dépendance manque — l'appelant décide quoi en faire."""
        mod, _, cls = self._fabrique.partition(":")
        import importlib
        return getattr(importlib.import_module(mod), cls)(dry_run=dry_run)


BINANCE = Venue(
    cle="binance", nom="Binance",
    env=("BINANCE_API_KEY", "BINANCE_API_SECRET"),
    portee="Crypto spot — taker 0,10 %, carnet profond",
    testnet_env="QUANT_BINANCE_TESTNET",
    notes="Bac à sable officiel par défaut (QUANT_BINANCE_TESTNET=1).",
    _fabrique="packages.execution.binance_broker:BinanceBroker",
)

BITMART = Venue(
    cle="bitmart", nom="Bitmart",
    env=("BITMART_API_KEY", "BITMART_API_SECRET"),
    portee="Crypto spot — taker 0,25 %",
    notes="Conservée pour compatibilité ; plus chère que Binance à rotation égale.",
    _fabrique="packages.execution.bitmart_broker:BitmartBroker",
)

PLACES: dict[str, Venue] = {v.cle: v for v in (BINANCE, BITMART)}
DEFAUT = "binance"


def venue_crypto() -> Venue:
    """La place crypto active. Un nom inconnu retombe sur le défaut plutôt que de planter :
    une faute de frappe dans une variable d'environnement ne doit pas priver de courtier."""
    choix = (os.environ.get("QUANT_CRYPTO_VENUE") or DEFAUT).strip().lower()
    return PLACES.get(choix, PLACES[DEFAUT])
