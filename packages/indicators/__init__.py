"""packages.indicators — 1 famille/fichier, 1 classe/indicateur, auto-enregistrés."""
from packages.indicators import (  # noqa: F401 (enregistrement)
    momentum,
    smc_lux_tp,
    trend,
    volatility,
)
from packages.indicators.registry import indicators

__all__ = ["indicators"]
