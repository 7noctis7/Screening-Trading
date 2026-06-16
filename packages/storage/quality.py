"""Contrats de qualité OHLCV — pipeline bloquant (Module 8).

Implémenté en pandas pur (les checks essentiels n'exigent pas pandera ;
on pourra brancher pandera/Great Expectations plus tard via la même API).
Un check critique en échec → `QualityError` (le pipeline s'arrête + alerte).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

_TF_FREQ = {"1m": "1min", "5m": "5min", "1h": "1h", "4h": "4h", "1d": "1D"}


class QualityError(Exception):
    pass


@dataclass
class QualityReport:
    symbol: str
    timeframe: str
    n_rows: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_ohlcv(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    max_staleness_hours: float | None = None,
    max_gap_ratio: float = 0.02,
) -> QualityReport:
    """Valide un DataFrame OHLCV indexé par ts (UTC). Colonnes: open/high/low/close/volume."""
    rep = QualityReport(symbol, timeframe, len(df))
    if df.empty:
        rep.errors.append("dataframe vide")
        return rep

    # 1) prix strictement positifs
    for col in ("open", "high", "low", "close"):
        if (df[col] <= 0).any():
            rep.errors.append(f"{col} <= 0 ({int((df[col] <= 0).sum())} lignes)")
    if (df["volume"] < 0).any():
        rep.errors.append("volume négatif")

    # 2) cohérence OHLC : high = max, low = min
    bad_high = (df["high"] < df[["open", "close", "low"]].max(axis=1)).sum()
    bad_low = (df["low"] > df[["open", "close", "high"]].min(axis=1)).sum()
    if bad_high:
        rep.errors.append(f"high < max(o,c,l) sur {int(bad_high)} lignes")
    if bad_low:
        rep.errors.append(f"low > min(o,c,h) sur {int(bad_low)} lignes")

    # 3) timestamps : uniques + strictement croissants
    if df.index.has_duplicates:
        rep.errors.append(f"{int(df.index.duplicated().sum())} timestamps dupliqués")
    if not df.index.is_monotonic_increasing:
        rep.errors.append("timestamps non croissants")

    # 4) trous temporels (warning au-delà du ratio)
    freq = _TF_FREQ.get(timeframe)
    if freq and len(df) > 2:
        expected = pd.date_range(df.index[0], df.index[-1], freq=freq)
        missing = len(expected) - len(df.index.intersection(expected))
        ratio = missing / max(1, len(expected))
        if ratio > max_gap_ratio:
            rep.warnings.append(f"{missing} barres manquantes ({ratio:.1%})")

    # 5) fraîcheur
    if max_staleness_hours is not None:
        last = df.index[-1]
        if last.tzinfo is None:
            last = last.tz_localize("UTC")
        age_h = (datetime.now(timezone.utc) - last.to_pydatetime()).total_seconds() / 3600
        if age_h > max_staleness_hours:
            rep.warnings.append(f"données périmées ({age_h:.1f}h > {max_staleness_hours}h)")

    return rep


def enforce(report: QualityReport) -> None:
    """Bloque le pipeline si le rapport contient des erreurs critiques."""
    if not report.ok:
        raise QualityError(
            f"[{report.symbol}/{report.timeframe}] qualité KO: {'; '.join(report.errors)}")
