"""Source iShares holdings (réseau requis) — la bonne façon gratuite d'obtenir
les constituants Russell : IWB = Russell 1000, IWV = Russell 3000.

iShares publie les holdings en CSV (préambule de quelques lignes puis table avec
colonnes Ticker / Name / Sector / Asset Class…). On saute le préambule, on garde
les lignes 'Equity', on ignore cash/dérivés. `dot_to_dash` → format Yahoo (BRK.B→BRK-B).
"""

from __future__ import annotations

import csv
import io

from packages.core.models import AssetClass, Instrument
from packages.data.universe.base import SourceError, constituent_sources


@constituent_sources.register("ishares_holdings")
class ISharesHoldingsSource:
    requires_network = True

    def __init__(self, id: str, url: str, venue: str = "US", currency: str = "USD",
                 dot_to_dash: bool = True, **_: object) -> None:
        self.id, self.url = id, url
        self.venue, self.currency, self.dot_to_dash = venue, currency, dot_to_dash

    def fetch(self) -> list[Instrument]:
        try:
            import urllib.request
            with urllib.request.urlopen(self.url, timeout=60) as r:
                text = r.read().decode("utf-8-sig")
        except Exception as e:  # noqa: BLE001
            raise SourceError(f"[{self.id}] iShares fetch échec: {e}") from e
        return self.parse(text)

    def parse(self, text: str) -> list[Instrument]:
        lines = text.splitlines()
        # trouver la ligne d'en-tête (celle qui contient 'Ticker')
        header_idx = next((i for i, ln in enumerate(lines)
                           if ln.lower().startswith('"ticker"') or ln.lower().startswith("ticker")),
                          None)
        if header_idx is None:
            raise SourceError(f"[{self.id}] en-tête 'Ticker' introuvable")
        reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
        out: list[Instrument] = []
        for row in reader:
            tkr = (row.get("Ticker") or "").strip().strip('"')
            asset = (row.get("Asset Class") or "").strip()
            if not tkr or tkr == "-" or asset and asset.lower() != "equity":
                continue
            sym = tkr.replace(".", "-") if self.dot_to_dash else tkr
            out.append(Instrument(symbol=sym, asset_class=AssetClass.EQUITY,
                                  venue=self.venue, currency=self.currency))
        if not out:
            raise SourceError(f"[{self.id}] aucune ligne Equity extraite")
        return out
