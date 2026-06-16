"""Registre des sizers. Choix de la méthode en YAML (config/risk.yaml)."""
from packages.core.interfaces import Sizer
from packages.core.registry import Registry

sizers: Registry[Sizer] = Registry("sizer")


def risk_per_unit(signal, price) -> float:
    """Distance prix→stop = risque par unité. 0 si pas de stop."""
    if signal.stop is None:
        return 0.0
    return abs(price - signal.stop)
