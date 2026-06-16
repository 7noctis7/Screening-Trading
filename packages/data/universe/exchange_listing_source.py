"""Source listing de bourse (réseau requis).

`nasdaq_trader` : listings COMPLETS US via les fichiers officiels pipe-delimités
(nasdaqlisted.txt = Nasdaq ; otherlisted.txt = NYSE/AMEX/ARCA). Des milliers de
symboles. Pour LSE/JPX/KRX/Borsa/SSE/SZSE : déclarer une source pointant sur leur
fichier de listing publié (même patron) — extension documentée (vault 05).
"""

from __future__ import annotations

import io

from packages.core.models import AssetClass, Instrument
from packages.data.universe.base import SourceError, constituent_sources

_NASDAQ = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
_OTHER = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


@constituent_sources.register("nasdaq_trader")
class NasdaqTraderSource:
    requires_network = True

    def __init__(self, id: str, include_etf: bool = True,
                 exclude_test_issues: bool = True, **_: object) -> None:
        self.id = id
        self.include_etf = include_etf
        self.exclude_test = exclude_test_issues

    def fetch(self) -> list[Instrument]:
        try:
            import urllib.request
            import pandas as pd
            out: list[Instrument] = []
            for url, sym_col, etf_col, venue in (
                (_NASDAQ, "Symbol", "ETF", "NASDAQ"),
                (_OTHER, "ACT Symbol", "ETF", "NYSE/AMEX"),
            ):
                with urllib.request.urlopen(url, timeout=30) as r:
                    raw = r.read().decode("utf-8")
                df = pd.read_csv(io.StringIO(raw), sep="|")
                df = df[~df[sym_col].astype(str).str.contains("File Creation", na=False)]
                if self.exclude_test and "Test Issue" in df.columns:
                    df = df[df["Test Issue"] != "Y"]
                for _, row in df.iterrows():
                    is_etf = str(row.get(etf_col, "")).upper() == "Y"
                    if is_etf and not self.include_etf:
                        continue
                    out.append(Instrument(
                        symbol=str(row[sym_col]).strip(),
                        asset_class=AssetClass.ETF if is_etf else AssetClass.EQUITY,
                        venue=venue, currency="USD"))
            return out
        except Exception as e:  # noqa: BLE001
            raise SourceError(f"[{self.id}] listing US échec: {e}") from e
