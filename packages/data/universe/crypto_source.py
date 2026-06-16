"""Source CoinGecko — top-N cryptos par market cap (réseau requis, API gratuite).

Exclut optionnellement les stablecoins/wrapped. Forme les paires BASE/quote.
"""

from __future__ import annotations

from packages.core.models import AssetClass, Instrument
from packages.data.universe.base import SourceError, constituent_sources

_URL = "https://api.coingecko.com/api/v3/coins/markets"
_STABLE = {"USDT", "USDC", "DAI", "TUSD", "USDD", "FDUSD", "USDE", "PYUSD"}


@constituent_sources.register("coingecko")
class CoinGeckoSource:
    requires_network = True

    def __init__(self, id: str, top_n: int = 100, quote: str = "USDT",
                 venue: str = "binance", exclude_stable: bool = True, **_: object) -> None:
        self.id, self.top_n, self.quote = id, top_n, quote
        self.venue, self.exclude_stable = venue, exclude_stable

    def fetch(self) -> list[Instrument]:
        try:
            import urllib.parse
            import urllib.request
            import json
            params = urllib.parse.urlencode({
                "vs_currency": "usd", "order": "market_cap_desc",
                "per_page": min(self.top_n * 2, 250), "page": 1})
            with urllib.request.urlopen(f"{_URL}?{params}", timeout=30) as r:
                rows = json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            raise SourceError(f"[{self.id}] CoinGecko échec: {e}") from e
        out: list[Instrument] = []
        for row in rows:
            base = str(row["symbol"]).upper()
            if self.exclude_stable and base in _STABLE:
                continue
            out.append(Instrument(symbol=f"{base}/{self.quote}",
                                  asset_class=AssetClass.CRYPTO, venue=self.venue,
                                  currency=self.quote, taker_fee_bps=10))
            if len(out) >= self.top_n:
                break
        return out
