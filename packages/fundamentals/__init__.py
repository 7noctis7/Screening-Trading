"""packages.fundamentals — ratios (Vernimmen) + valorisation (Damodaran) + facteurs."""
from packages.fundamentals import factors, ratios, valuation  # noqa: F401 (enregistrement)
from packages.fundamentals.models import Financials
from packages.fundamentals.fmp_provider import FMPFundamentalsProvider, build_financials
from packages.fundamentals.provider import (
    FundamentalsProvider,
    SyntheticFundamentalsProvider,
)

__all__ = [
    "Financials", "FundamentalsProvider", "SyntheticFundamentalsProvider",
    "ratios", "valuation", "FMPFundamentalsProvider", "build_financials",
]
