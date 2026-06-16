"""Source statique — lit un CSV seed (offline). Pour forex/commodities/indices/
crypto-top100/CAC40/AEX. Colonnes : symbol,name,asset_class,venue,currency[,...]."""

from __future__ import annotations

import csv
from pathlib import Path

from packages.core.models import AssetClass, Instrument
from packages.data.universe.base import SourceError, constituent_sources


@constituent_sources.register("static")
class StaticSource:
    requires_network = False

    def __init__(self, id: str, file: str, **_: object) -> None:
        self.id = id
        self.file = file

    def fetch(self) -> list[Instrument]:
        p = Path(self.file)
        if not p.exists():
            raise SourceError(f"seed introuvable: {p}")
        out: list[Instrument] = []
        with p.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                out.append(Instrument(
                    symbol=row["symbol"].strip(),
                    asset_class=AssetClass(row["asset_class"].strip()),
                    venue=row.get("venue", "UNKNOWN").strip(),
                    currency=row.get("currency", "USD").strip(),
                    taker_fee_bps=float(row.get("taker_fee_bps", 0) or 0),
                ))
        return out
