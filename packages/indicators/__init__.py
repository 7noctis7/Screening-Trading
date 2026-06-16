"""packages.indicators — 1 famille/fichier, 1 classe/indicateur, auto-enregistrés."""
from packages.indicators import momentum, trend, volatility  # noqa: F401 (enregistrement)
from packages.indicators.registry import indicators

__all__ = ["indicators"]
