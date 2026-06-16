"""Chargement de l'univers depuis config/universe.yaml → list[Instrument].

Sépare les actifs TRADABLES des BENCHMARKS (indices de comparaison, non tradés
par les stratégies mais utilisés pour l'attribution relative — Module 7).
"""

from __future__ import annotations

from pathlib import Path

from packages.common.config import load_yaml
from packages.core.models import AssetClass, Instrument

# Indices traités comme benchmarks par défaut (comparaison, pas trading)
_BENCHMARK_CLASSES = {AssetClass.INDEX}


def load_universe(path: str | Path) -> list[Instrument]:
    raw = load_yaml(path).get("instruments", [])
    out: list[Instrument] = []
    for row in raw:
        out.append(Instrument(
            symbol=row["symbol"],
            asset_class=AssetClass(row["asset_class"]),
            venue=row.get("venue", "UNKNOWN"),
            currency=row.get("currency", "USD"),
            tz=row.get("tz", "UTC"),
            taker_fee_bps=float(row.get("taker_fee_bps", 0.0)),
            maker_fee_bps=float(row.get("maker_fee_bps", 0.0)),
        ))
    return out


def tradable(instruments: list[Instrument]) -> list[Instrument]:
    return [i for i in instruments if i.asset_class not in _BENCHMARK_CLASSES]


def benchmarks(instruments: list[Instrument]) -> list[Instrument]:
    return [i for i in instruments if i.asset_class in _BENCHMARK_CLASSES]
