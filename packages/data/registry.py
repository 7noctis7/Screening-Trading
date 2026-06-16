"""Registre des sources de données. Brancher une source = 1 fichier + @data_providers.register."""
from packages.core.interfaces import DataProvider
from packages.core.registry import Registry

data_providers: Registry[DataProvider] = Registry("data_provider")
