"""packages.portfolio.sizing — 1 méthode/fichier, choix en YAML."""
from packages.portfolio.sizing import fixed_fractional, vol_target  # noqa: F401
from packages.portfolio.sizing.registry import sizers

__all__ = ["sizers"]
