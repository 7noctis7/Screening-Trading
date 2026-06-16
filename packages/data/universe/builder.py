"""UniverseBuilder — orchestre les sources, dédoublonne, produit un snapshot daté.

Lit `config/universe.yaml` (liste de sources). Pour chaque source activée :
instancie via le registry (kind → classe), `fetch()`, collecte. Dédoublonnage par
`(symbol, venue)`. Les sources réseau qui échouent hors-ligne sont **sautées
proprement** (loggées, jamais bloquantes) → le build offline produit l'univers
statique, le build en ligne le complète.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from packages.common.config import load_yaml
from packages.common.logging import get_logger
from packages.core.models import Instrument
from packages.data.universe.base import SourceError, constituent_sources

# importe les modules → enregistre les sources
from packages.data.universe import (  # noqa: F401
    crypto_source,
    exchange_listing_source,
    ishares_source,
    static_source,
    wikipedia_source,
)

log = get_logger("universe.builder")


@dataclass
class BuildResult:
    instruments: list[Instrument]
    as_of: datetime
    per_source: dict[str, int] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    duplicates_removed: int = 0


class UniverseBuilder:
    def __init__(self, config_path: str | Path, allow_network: bool = True) -> None:
        self.config_path = Path(config_path)
        self.allow_network = allow_network

    def build(self) -> BuildResult:
        sources_cfg = load_yaml(self.config_path).get("sources", [])
        seen: dict[str, Instrument] = {}          # clé = symbole normalisé
        per_source: dict[str, int] = {}
        skipped: list[str] = []
        duplicates = 0
        for cfg in sources_cfg:
            if not cfg.get("enabled", True):
                continue
            sid, kind = cfg.get("id", "?"), cfg.get("kind")
            try:
                source = constituent_sources.create(kind, **cfg)
            except KeyError:
                log.warning("source inconnue", extra={"extra": {"id": sid, "kind": kind}})
                skipped.append(sid)
                continue
            if source.requires_network and not self.allow_network:
                skipped.append(sid)
                log.debug("source réseau sautée (offline)", extra={"extra": {"id": sid}})
                continue
            try:
                fetched = source.fetch()
            except SourceError as e:
                skipped.append(sid)
                log.warning("source en échec", extra={"extra": {"id": sid, "err": str(e)[:120]}})
                continue
            added = 0
            for inst in fetched:
                key = inst.symbol.strip().upper()      # dédoublonnage par SYMBOLE
                if key in seen:
                    duplicates += 1                    # priorité = 1re source vue
                    continue
                seen[key] = inst
                added += 1
            per_source[sid] = added
        result = BuildResult(list(seen.values()), datetime.now(timezone.utc),
                             per_source, skipped, duplicates)
        log.info("univers construit", extra={"extra": {
            "total": len(result.instruments), "doublons_retires": duplicates,
            "sources": per_source, "skipped": skipped}})
        return result
