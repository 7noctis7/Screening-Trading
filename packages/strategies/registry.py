"""Registre des stratégies. Ajouter une stratégie = 1 fichier + @strategies.register."""
from packages.core.interfaces import Strategy
from packages.core.registry import Registry

strategies: Registry[Strategy] = Registry("strategy")
