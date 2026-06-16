"""packages.strategies — 1 stratégie/fichier, plugin auto-enregistré."""
from packages.strategies import ma_crossover, rsi_reversion, swing  # noqa: F401
from packages.strategies.registry import strategies

__all__ = ["strategies"]
