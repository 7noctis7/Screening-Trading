"""Registre des indicateurs. Ajouter un indicateur = 1 classe + @indicators.register."""
from packages.core.interfaces import Indicator
from packages.core.registry import Registry

indicators: Registry[Indicator] = Registry("indicator")


def closes(bars) -> list[float]:
    return [b.close for b in bars]
