"""packages.data — adaptateurs DataProvider (1 fichier/source, auto-enregistrés)."""
from packages.data.providers import synthetic, yfinance_provider  # noqa: F401 (enregistrement)
from packages.data.providers.wrappers import (
    CachingProvider, FallbackProvider, RateLimitedProvider, RateLimiter,
)
from packages.data.registry import data_providers

__all__ = ["data_providers", "CachingProvider", "FallbackProvider",
           "RateLimitedProvider", "RateLimiter"]
