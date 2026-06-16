"""packages.core — domaine pur (interfaces + models). ZÉRO dépendance externe.

Rien dans ce package ne doit importer pandas, requests, fastapi, etc.
C'est la garantie que le domaine ne dépend jamais de l'API, la DB ou l'UI.
"""

from packages.core.interfaces import (
    Broker,
    DataProvider,
    Factor,
    Indicator,
    RiskDecision,
    RiskRule,
    Sizer,
    Strategy,
)
from packages.core.models import (
    AssetClass,
    Bar,
    CyclePhase,
    FactorScore,
    EconomicRelease,
    Instrument,
    MacroObservation,
    Order,
    OrderStatus,
    OrderType,
    Position,
    RegimeState,
    RiskMode,
    Side,
    Signal,
    SignalDirection,
    TradeRecord,
)
from packages.core.registry import Registry

__all__ = [
    "AssetClass", "Bar", "Broker", "CyclePhase", "DataProvider", "Factor",
    "EconomicRelease", "FactorScore", "Indicator", "Instrument",
    "MacroObservation", "Order", "OrderStatus",
    "OrderType", "Position", "RegimeState", "Registry", "RiskDecision",
    "RiskMode", "RiskRule", "Side", "Signal", "SignalDirection", "Sizer",
    "Strategy", "TradeRecord",
]
