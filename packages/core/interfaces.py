"""Interfaces du domaine (Protocols / ABC).

Tout le système **dépend de ces abstractions**, jamais des implémentations
concrètes. On branche/débranche un provider, un broker, une stratégie sans
toucher au reste (cf. 01_ARCHITECTURE.md, règles d'or 3).

Volontairement regroupées dans un seul fichier *de contrats* : ce sont des
signatures, pas de la logique. Les **implémentations** vivent chacune dans
leur propre fichier (1 responsabilité / fichier).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence, runtime_checkable

from packages.core.models import (
    Bar,
    FactorScore,
    Order,
    Position,
    RegimeState,
    Signal,
)


@runtime_checkable
class DataProvider(Protocol):
    """Source de données marché (yfinance, Finnhub, CCXT, Alpaca...)."""

    name: str

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime | None = None,
    ) -> Sequence[Bar]:
        """Renvoie des barres OHLCV normalisées (UTC). Aucun look-ahead."""
        ...

    def supports(self, symbol: str) -> bool:
        ...


@runtime_checkable
class Indicator(Protocol):
    """Indicateur technique. Calculé uniquement sur l'info disponible à `t`."""

    name: str

    def compute(self, bars: Sequence[Bar]) -> list[float]:
        """Série alignée sur `bars` (NaN tant que la fenêtre n'est pas pleine)."""
        ...


@runtime_checkable
class Factor(Protocol):
    """Facteur (technique / fondamental / valo) → score cross-sectional."""

    name: str
    asset_classes: Sequence[str]  # un facteur absent pour une classe = poids nul

    def compute(self, as_of: datetime) -> list[FactorScore]:
        ...


@runtime_checkable
class Strategy(Protocol):
    """Stratégie plugin. Émet des Signals ; n'exécute jamais d'ordre."""

    name: str
    favorable_regime: str  # "trending", "range", "any"...

    def generate_signals(
        self, bars: Sequence[Bar], regime: RegimeState | None = None
    ) -> list[Signal]:
        ...


@runtime_checkable
class Sizer(Protocol):
    """Calcule la taille de position (fixed-fractional, vol-target, Kelly bridé...)."""

    name: str

    def size(
        self,
        signal: Signal,
        equity: float,
        price: float,
        regime: RegimeState | None = None,
    ) -> float:
        """Quantité à trader. Jamais 'tout-in'."""
        ...


class RiskDecision:
    """Verdict du risk engine : accepté ou veto motivé."""

    __slots__ = ("approved", "reason")

    def __init__(self, approved: bool, reason: str = "") -> None:
        self.approved = approved
        self.reason = reason

    @classmethod
    def ok(cls) -> "RiskDecision":
        return cls(True)

    @classmethod
    def veto(cls, reason: str) -> "RiskDecision":
        return cls(False, reason)


@runtime_checkable
class RiskRule(Protocol):
    """Règle de risque à droit de veto. 1 règle = 1 fichier."""

    name: str

    def check(
        self,
        order: Order,
        positions: Sequence[Position],
        equity: float,
        regime: RegimeState | None = None,
    ) -> RiskDecision:
        ...


@runtime_checkable
class Broker(Protocol):
    """Broker / exchange (Alpaca, CCXT...). Paper par défaut."""

    name: str
    is_paper: bool

    def submit(self, order: Order) -> Order:
        """Idempotent via order.client_id."""
        ...

    def positions(self) -> list[Position]:
        ...

    def equity(self) -> float:
        ...

    def cancel(self, client_id: str) -> bool:
        ...
