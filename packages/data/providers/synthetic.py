"""Provider synthétique — mouvement brownien géométrique seedé.

Aucune dépendance réseau, 100 % reproductible (seed). Sert aux démos et aux
tests d'intégration : la parité backtest↔live n'exige pas de vraie donnée pour
être validée structurellement.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np

from packages.core.models import Bar
from packages.data.registry import data_providers

_TF_SECONDS = {"1m": 60, "5m": 300, "1h": 3600, "1d": 86400}


def _stable_seed(symbol: str) -> int:
    """Seed déterministe par symbole (hashlib, PAS hash() qui est randomisé/process)."""
    digest = hashlib.sha256(symbol.encode()).hexdigest()
    return int(digest[:8], 16) % 10_000


@data_providers.register("synthetic")
class SyntheticProvider:
    name = "synthetic"

    def __init__(
        self,
        seed: int = 42,
        start_price: float = 100.0,
        annual_vol: float = 0.25,
        drift: float = 0.06,
    ) -> None:
        self.seed = seed
        self.start_price = start_price
        self.annual_vol = annual_vol
        self.drift = drift

    def supports(self, symbol: str) -> bool:
        return True

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Bar]:
        end = end or datetime.now(timezone.utc)
        step = _TF_SECONDS.get(timeframe, 86400)
        n = max(1, int((end - start).total_seconds() // step))
        # seed dérivé du symbole → chaque actif a sa propre trajectoire stable
        rng = np.random.default_rng(self.seed + _stable_seed(symbol))
        dt = step / (252 * 86400)
        mu = (self.drift - 0.5 * self.annual_vol**2) * dt
        sigma = self.annual_vol * np.sqrt(dt)
        rets = rng.normal(mu, sigma, n)
        close = self.start_price * np.exp(np.cumsum(rets))
        open_ = np.concatenate([[self.start_price], close[:-1]])
        intra = np.abs(rng.normal(0, sigma, n)) * close
        high = np.maximum(open_, close) + intra
        low = np.minimum(open_, close) - intra
        vol = rng.uniform(1e5, 5e5, n)
        bars: list[Bar] = []
        for i in range(n):
            ts = start + timedelta(seconds=step * (i + 1))
            bars.append(
                Bar(symbol, timeframe, ts, float(open_[i]), float(high[i]),
                    float(low[i]), float(close[i]), float(vol[i]))
            )
        return bars
