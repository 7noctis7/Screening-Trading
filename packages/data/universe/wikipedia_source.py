"""Source Wikipédia — constituants d'indices via `pandas.read_html` (réseau requis).

Couvre S&P 500, Nasdaq-100, CAC 40, FTSE 100, FTSE MIB, AEX, Nikkei 225, KOSPI…
en pointant l'URL + l'index de table + les colonnes en config. `suffix` ajoute le
suffixe Yahoo (.PA, .L, .MI, .T, .KS, .AS, .HK, .SS…). `dot_to_dash` gère BRK.B→BRK-B.
"""

from __future__ import annotations

from packages.core.models import AssetClass, Instrument
from packages.data.universe.base import SourceError, constituent_sources


@constituent_sources.register("wikipedia")
class WikipediaSource:
    requires_network = True

    def __init__(self, id: str, url: str, symbol_col: str, name_col: str | None = None,
                 sector_col: str | None = None, table: int = 0, suffix: str = "",
                 asset_class: str = "equity", venue: str = "UNKNOWN",
                 currency: str = "USD", dot_to_dash: bool = False, **_: object) -> None:
        self.id, self.url, self.table = id, url, table
        self.symbol_col, self.name_col, self.sector_col = symbol_col, name_col, sector_col
        self.suffix, self.asset_class = suffix, AssetClass(asset_class)
        self.venue, self.currency, self.dot_to_dash = venue, currency, dot_to_dash

    def fetch(self) -> list[Instrument]:
        try:
            import pandas as pd
            tables = pd.read_html(self.url)
        except Exception as e:  # noqa: BLE001
            raise SourceError(f"[{self.id}] read_html échec: {e}") from e
        if self.table >= len(tables):
            raise SourceError(f"[{self.id}] table {self.table} absente ({len(tables)} trouvées)")
        df = tables[self.table]
        if self.symbol_col not in df.columns:
            raise SourceError(f"[{self.id}] colonne '{self.symbol_col}' absente: {list(df.columns)}")
        out: list[Instrument] = []
        for raw in df[self.symbol_col].astype(str):
            sym = raw.strip().replace(".", "-") if self.dot_to_dash else raw.strip()
            out.append(Instrument(symbol=sym + self.suffix, asset_class=self.asset_class,
                                  venue=self.venue, currency=self.currency))
        return out
