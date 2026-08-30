"""packages.strategies — 1 stratégie/fichier, plugin auto-enregistré."""

from packages.strategies import (  # noqa: F401
    institutional_price_action,
    ma_crossover,
    rsi_reversion,
    swing,
)
from packages.strategies.registry import strategies

__all__ = ["strategies"]
